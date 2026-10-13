"""The two Hanjeok endpoints the guide may call, and nothing else.

`GET /api/v1/attractions/{id}/congestion` and `…/alternatives`. Both are
read-only. `GET /api/v1/attractions/{id}` is deliberately absent: it records a
detail-view event on every call, so calling it would write to the service and
inflate its statistics (spec FR-016).

Three modes. `live` calls Hanjeok. `record` calls it and keeps each response in
a directory. `replay` answers only from such a directory and makes no network
call at all — that is how tests run, how an evaluation gives both strategies
the same facts, and how the demo runs with no Hanjeok behind it.

Responses are reduced to the fields below before anything else sees them.
Hanjeok returns more — image addresses, visitor-feedback tallies — and what is
not carried here cannot reach a prompt or an answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

GRADES = ("RELAXED", "NORMAL", "CROWDED", "VERY_CROWDED")


class LiveError(Exception):
    CAUSES = ("unknown_place", "service_unreachable")

    def __init__(self, cause: str, detail: str = "") -> None:
        assert cause in self.CAUSES, cause
        super().__init__(f"{cause}: {detail}" if detail else cause)
        self.cause = cause


@dataclass(frozen=True, slots=True)
class DayForecast:
    date: str
    grade: str
    concentration: float


@dataclass(frozen=True, slots=True)
class Congestion:
    place_id: int
    date: str
    name: str
    fetched_at: str
    has_data: bool
    """False is its own outcome: Hanjeok does not forecast this place. It is
    never a grade, and in particular never "relaxed"."""

    grade: str | None = None
    concentration: float | None = None
    percentile: float | None = None
    better_dates: tuple[DayForecast, ...] = ()


@dataclass(frozen=True, slots=True)
class Alternative:
    place_id: int
    name: str
    grade: str
    concentration: float
    distance_km: float | None
    travel_minutes: float | None


@dataclass(frozen=True, slots=True)
class Alternatives:
    place_id: int
    date: str
    fetched_at: str
    items: tuple[Alternative, ...]
    """In the order Hanjeok returned them. That order is the ranking; nothing
    downstream sorts this."""


def _unwrap(status: int, body: Any) -> dict | list:
    """Hanjeok's `{success, data, error}` envelope."""
    if not isinstance(body, dict):
        raise LiveError("service_unreachable", f"HTTP {status}, not an envelope")
    if status == 404 or (body.get("error") or {}).get("code") == "ATTRACTION_NOT_FOUND":
        raise LiveError("unknown_place")
    if status != 200 or not body.get("success") or body.get("data") is None:
        raise LiveError("service_unreachable", f"HTTP {status}")
    return body["data"]


def _grade(value: Any) -> str:
    if value not in GRADES:
        raise LiveError("service_unreachable", "a grade outside the four Hanjeok defines")
    return value


def parse_congestion(
    place_id: int, day: str, status: int, body: Any, fetched_at: str
) -> Congestion:
    data = _unwrap(status, body)
    try:
        name = data["attraction"]["name"]
        if data["hasCongestionData"] is False:
            return Congestion(place_id, day, name, fetched_at, has_data=False)
        diagnosis = data["diagnosis"]
        return Congestion(
            place_id,
            day,
            name,
            fetched_at,
            has_data=True,
            grade=_grade(diagnosis["grade"]),
            concentration=float(diagnosis["concentration"]),
            percentile=float(diagnosis["percentile"]),
            better_dates=tuple(
                DayForecast(item["date"], _grade(item["grade"]), float(item["concentration"]))
                for item in data.get("betterDates", [])
            ),
        )
    except (KeyError, TypeError, ValueError):
        raise LiveError(
            "service_unreachable", "congestion response is not the documented shape"
        ) from None


def parse_alternatives(
    place_id: int, day: str, status: int, body: Any, fetched_at: str
) -> Alternatives:
    data = _unwrap(status, body)
    try:
        items = tuple(
            Alternative(
                int(item["attractionId"]),
                item["name"],
                _grade(item["grade"]),
                float(item["concentration"]),
                item.get("distanceKm"),
                item.get("travelMinutes"),
            )
            for item in data
        )
    except (KeyError, TypeError, ValueError):
        raise LiveError(
            "service_unreachable", "alternatives response is not the documented shape"
        ) from None
    return Alternatives(place_id, day, fetched_at, items)


class Recording:
    """A directory of responses, one file per call, plus the day they were made.

    The day matters: "this Saturday" resolves against today, and a recording
    only holds the dates that were asked about on its day. Replaying it means
    replaying that day, so `today` is read from here in replay mode.
    """

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    @property
    def _meta(self) -> Path:
        return self.directory / "recording.json"

    def today(self) -> date | None:
        if not self._meta.is_file():
            return None
        return date.fromisoformat(json.loads(self._meta.read_text("utf-8"))["today"])

    def start(self, today: date) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self._meta.is_file():
            self._meta.write_text(
                json.dumps(
                    {"today": today.isoformat(), "recorded_at": datetime.now(UTC).isoformat()}
                )
                + "\n",
                "utf-8",
            )

    def _path(self, kind: str, place_id: int, day: str) -> Path:
        # Both parts are validated before they get here (an int, an ISO date),
        # so this cannot name a file outside the directory.
        return self.directory / f"{kind}-{int(place_id)}-{date.fromisoformat(day).isoformat()}.json"

    def load(self, kind: str, place_id: int, day: str) -> dict | None:
        path = self._path(kind, place_id, day)
        return json.loads(path.read_text("utf-8")) if path.is_file() else None

    def save(
        self, kind: str, place_id: int, day: str, status: int, body: Any, fetched_at: str
    ) -> None:
        self._path(kind, place_id, day).write_text(
            json.dumps(
                {"status": status, "fetched_at": fetched_at, "body": body},
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            "utf-8",
        )


class LiveClient:
    def __init__(
        self,
        *,
        mode: str = "live",
        base_url: str = "",
        recording: Recording | None = None,
        http=None,
        timeout: float = 5.0,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        if mode not in ("live", "record", "replay"):
            raise ValueError(f"unknown live mode: {mode}")
        if mode != "live" and recording is None:
            raise ValueError(f"{mode} mode needs a recording directory")
        if mode != "replay" and not base_url:
            raise ValueError(f"{mode} mode needs the Hanjeok base URL")
        self.mode, self.recording, self._clock = mode, recording, clock
        self._base_url, self._timeout, self._http = base_url.rstrip("/"), timeout, http

    def today(self) -> date:
        """Hanjeok's forecasts are dated in Korean time. In replay, the
        recording's day."""
        if self.mode == "replay":
            recorded = self.recording.today()
            if recorded is not None:
                return recorded
        from zoneinfo import ZoneInfo

        return self._clock().astimezone(ZoneInfo("Asia/Seoul")).date()

    def _get(self, kind: str, place_id: int, day: str) -> tuple[int, Any, str]:
        if self.mode == "replay":
            saved = self.recording.load(kind, place_id, day)
            if saved is None:
                # Not "no data": the recording simply does not hold this call.
                raise LiveError("service_unreachable", "not in the recording")
            return saved["status"], saved["body"], saved["fetched_at"]

        import httpx

        http = self._http or httpx
        fetched_at = self._clock().isoformat().replace("+00:00", "Z")
        try:
            # Exactly these two paths, built from an int and a validated date.
            response = http.get(
                f"{self._base_url}/api/v1/attractions/{int(place_id)}/{kind}",
                params={"date": day},
                timeout=self._timeout,
            )
            status, body = response.status_code, response.json()
        except (httpx.HTTPError, ValueError):
            raise LiveError("service_unreachable", "request failed") from None
        if self.mode == "record":
            self.recording.start(self.today())
            self.recording.save(kind, place_id, day, status, body, fetched_at)
        return status, body, fetched_at

    def congestion(self, place_id: int, day: str) -> Congestion:
        status, body, fetched_at = self._get("congestion", place_id, day)
        return parse_congestion(place_id, day, status, body, fetched_at)

    def alternatives(self, place_id: int, day: str) -> Alternatives:
        status, body, fetched_at = self._get("alternatives", place_id, day)
        return parse_alternatives(place_id, day, status, body, fetched_at)
