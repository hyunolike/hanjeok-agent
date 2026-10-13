"""Read a Hanjeok export, and refuse one that is not what its manifest says.

The export is the only way Hanjeok data enters this repository
(`specs/002-hanjeok-guide-agent/contracts/hanjeok-export.md`). Everything is
checked before anything is loaded: a refresh that discovers a truncated file
halfway through writing the graph has already done damage.

Columns are an allow-list **here too**, not only in the script that produces the
export. If a column the contract does not name ever appears — a phone number, a
member id — the read stops. Data the agent must not answer from is better never
held, and "the exporter would not do that" is not a check.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1

_NUMBER = (int, float)

# field -> (accepted types, nullable)
_PLACE = {
    "id": (int, False),
    "name": (str, False),
    "region_code": (str, True),
    "region_label": (str, True),
    "content_type": (str, True),
    "category_mid": (str, True),
    "category_small": (str, True),
    "summary": (str, True),
    "overview": (str, True),
    "address": (str, True),
    "lat": (_NUMBER, True),
    "lng": (_NUMBER, True),
    "has_congestion_data": (bool, False),
}
_RELATED = {
    "base_id": (int, False),
    "related_id": (int, False),
    "rank": (int, True),
    "score": (_NUMBER, True),
    "distance_km": (_NUMBER, True),
    "travel_minutes": (_NUMBER, True),
}
_FESTIVAL = {
    "id": ((int, str), False),
    "name": (str, False),
    "start_date": (str, False),
    "end_date": (str, False),
    "lat": (_NUMBER, True),
    "lng": (_NUMBER, True),
}
_EXHIBITION = {**_FESTIVAL, "place": (str, True), "attraction_id": (int, True)}

FILES = {
    "places.jsonl": _PLACE,
    "related.jsonl": _RELATED,
    "festivals.jsonl": _FESTIVAL,
    "exhibitions.jsonl": _EXHIBITION,
}


class ExportError(Exception):
    """An export that must not be loaded. `cause` is from a fixed list so the
    command line and the tests can name what went wrong without parsing prose."""

    CAUSES = (
        "manifest_missing",
        "manifest_invalid",
        "format_version_unsupported",
        "file_missing",
        "hash_mismatch",
        "row_count_mismatch",
        "row_invalid",
        "unexpected_column",
        "duplicate_id",
        "dangling_reference",
    )

    def __init__(self, cause: str, detail: str) -> None:
        assert cause in self.CAUSES, cause
        super().__init__(f"{cause}: {detail}")
        self.cause = cause
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Place:
    id: int
    name: str
    region_code: str | None
    region_label: str | None
    content_type: str | None
    category_mid: str | None
    category_small: str | None
    summary: str | None
    overview: str | None
    address: str | None
    lat: float | None
    lng: float | None
    has_congestion_data: bool


@dataclass(frozen=True, slots=True)
class Related:
    base_id: int
    related_id: int
    rank: int | None
    score: float | None
    distance_km: float | None
    travel_minutes: float | None


@dataclass(frozen=True, slots=True)
class Event:
    id: str
    """Prefixed with its kind (`festival:…`, `exhibition:…`) so the two files
    cannot collide and a citation names which one it is."""

    kind: str
    name: str
    start_date: str
    end_date: str
    lat: float | None
    lng: float | None
    place_text: str | None = None
    place_id: int | None = None


@dataclass(frozen=True, slots=True)
class Export:
    exported_at: str
    source: str
    sha256: str
    """SHA-256 of `manifest.json`. One value that names the whole export, since
    the manifest holds every other file's hash."""

    places: tuple[Place, ...]
    related: tuple[Related, ...]
    events: tuple[Event, ...]

    @property
    def regions(self) -> dict[str, str]:
        """code -> label, for every place that has a code."""
        return {
            p.region_code: p.region_label or p.region_code for p in self.places if p.region_code
        }

    @property
    def counts(self) -> dict[str, int]:
        return {
            "places": len(self.places),
            "related": len(self.related),
            "events": len(self.events),
            "regions": len(self.regions),
        }


def _rows(path: Path, name: str, columns: dict, expected: dict[str, Any]) -> list[dict]:
    if not path.is_file():
        raise ExportError("file_missing", name)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected.get("sha256"):
        raise ExportError(
            "hash_mismatch", f"{name}: manifest says {expected.get('sha256')}, file is {digest}"
        )

    rows: list[dict] = []
    for number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ExportError("row_invalid", f"{name}:{number}: {error.msg}") from None
        if not isinstance(row, dict):
            raise ExportError("row_invalid", f"{name}:{number}: not an object")
        extra = sorted(set(row) - set(columns))
        if extra:
            # Named, never printed with its value: the value is exactly what
            # should not end up in a terminal or a CI log.
            raise ExportError("unexpected_column", f"{name}:{number}: {', '.join(extra)}")
        for field, (types, nullable) in columns.items():
            value = row.get(field)
            if value is None:
                if not nullable:
                    raise ExportError("row_invalid", f"{name}:{number}: {field} is required")
            # bool is an int in Python; a `true` where a number belongs is a bug.
            elif not isinstance(value, types) or (isinstance(value, bool) and types is not bool):
                raise ExportError("row_invalid", f"{name}:{number}: {field} has the wrong type")
        rows.append(row)

    if len(rows) != expected.get("rows"):
        raise ExportError(
            "row_count_mismatch",
            f"{name}: manifest says {expected.get('rows')}, file has {len(rows)}",
        )
    return rows


def _dates(row: dict, name: str) -> None:
    try:
        start, end = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
    except ValueError:
        raise ExportError(
            "row_invalid", f"{name}: {row['id']} has a date that is not YYYY-MM-DD"
        ) from None
    if end < start:
        raise ExportError("row_invalid", f"{name}: {row['id']} ends before it starts")


def read_export(directory: Path | str) -> Export:
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ExportError("manifest_missing", str(manifest_path))
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
        files = manifest["files"]
        exported_at = manifest["exported_at"]
        datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
        version = manifest["format_version"]
        if not all(isinstance(files[name], dict) for name in FILES):
            raise TypeError
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ExportError(
            "manifest_invalid", "manifest.json does not have the fields of the contract"
        ) from None
    if version != FORMAT_VERSION:
        raise ExportError(
            "format_version_unsupported", f"{version!r}; this reader understands {FORMAT_VERSION}"
        )

    raw = {
        name: _rows(directory / name, name, columns, files[name]) for name, columns in FILES.items()
    }

    places = tuple(
        Place(**{field: row.get(field) for field in _PLACE}) for row in raw["places.jsonl"]
    )
    ids = [p.id for p in places]
    if len(set(ids)) != len(ids):
        raise ExportError("duplicate_id", "places.jsonl has the same id twice")
    known = set(ids)

    related = tuple(
        Related(**{field: row.get(field) for field in _RELATED}) for row in raw["related.jsonl"]
    )
    seen: set[tuple[int, int]] = set()
    for link in related:
        # The contract promises both ends are in places.jsonl. A link to a
        # place the agent cannot name would surface as an alternative with no
        # name, so it is refused here instead.
        if link.base_id not in known or link.related_id not in known:
            raise ExportError(
                "dangling_reference", f"related.jsonl: {link.base_id} -> {link.related_id}"
            )
        if (link.base_id, link.related_id) in seen:
            raise ExportError(
                "duplicate_id", f"related.jsonl: {link.base_id} -> {link.related_id} twice"
            )
        seen.add((link.base_id, link.related_id))

    events: list[Event] = []
    for kind, name in (("festival", "festivals.jsonl"), ("exhibition", "exhibitions.jsonl")):
        for row in raw[name]:
            _dates(row, name)
            place_id = row.get("attraction_id")
            events.append(
                Event(
                    id=f"{kind}:{row['id']}",
                    kind=kind,
                    name=row["name"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    lat=row.get("lat"),
                    lng=row.get("lng"),
                    place_text=row.get("place"),
                    # An exhibition tied to a place that was not exported keeps
                    # its text and loses the tie. That is not an error: the
                    # export only carries covered places and their neighbours.
                    place_id=place_id if place_id in known else None,
                )
            )
    event_ids = [e.id for e in events]
    if len(set(event_ids)) != len(event_ids):
        raise ExportError("duplicate_id", "an event id appears twice")

    return Export(
        exported_at=exported_at,
        source=str(manifest.get("source", "")),
        sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        places=places,
        related=related,
        events=tuple(events),
    )
