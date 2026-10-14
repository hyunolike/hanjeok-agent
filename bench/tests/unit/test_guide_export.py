"""An export is loaded whole or not at all, and says why when it is not."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from guide.export import ExportError, read_export

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOOD = FIXTURES / "hanjeok-export"


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    target = tmp_path / "export"
    shutil.copytree(GOOD, target)
    return target


def rewrite(directory: Path, name: str, change) -> None:
    """Change a file's rows and bring the manifest back in step, so the test
    reaches the check it is about instead of stopping at the hash."""
    rows = [json.loads(line) for line in (directory / name).read_text("utf-8").splitlines()]
    rows = change(rows) or rows
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
    (directory / name).write_bytes(data)
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    manifest["files"][name] = {"rows": len(rows), "sha256": hashlib.sha256(data).hexdigest()}
    (directory / "manifest.json").write_text(json.dumps(manifest), "utf-8")


def cause_of(directory: Path) -> str:
    with pytest.raises(ExportError) as caught:
        read_export(directory)
    return caught.value.cause


def test_the_synthetic_export_reads_and_counts_match_its_manifest():
    export = read_export(GOOD)

    assert export.counts == {"places": 40, "related": 54, "events": 5, "regions": 2}
    assert export.exported_at == "2026-10-13T02:00:00Z"
    assert len(export.sha256) == 64
    assert export.regions == {"11110": "한빛시 가람구", "11140": "한빛시 솔내구"}


def test_it_has_the_cases_the_agent_must_handle():
    export = read_export(GOOD)
    by_name: dict[str, list] = {}
    for place in export.places:
        by_name.setdefault(place.name, []).append(place)

    assert len(by_name["은행나무길"]) == 2, "two places sharing a name"
    assert not next(p for p in export.places if p.id == 150).has_congestion_data
    assert any(link.rank is None for link in export.related), "a link Hanjeok did not rank"
    assert {e.kind for e in export.events} == {"festival", "exhibition"}
    assert next(e for e in export.events if e.id == "exhibition:old-maps").place_id == 161


def test_the_broken_copy_is_refused_and_names_the_file():
    with pytest.raises(ExportError) as caught:
        read_export(FIXTURES / "hanjeok-export-broken")

    assert caught.value.cause == "hash_mismatch"
    assert "related.jsonl" in caught.value.detail


def test_a_missing_manifest(export_dir: Path):
    (export_dir / "manifest.json").unlink()
    assert cause_of(export_dir) == "manifest_missing"


@pytest.mark.parametrize(
    "text", ["not json", "{}", '{"format_version": 1, "exported_at": "yesterday", "files": {}}']
)
def test_a_manifest_without_the_contract_fields(export_dir: Path, text: str):
    (export_dir / "manifest.json").write_text(text, "utf-8")
    assert cause_of(export_dir) == "manifest_invalid"


def test_a_format_this_reader_does_not_know(export_dir: Path):
    manifest = json.loads((export_dir / "manifest.json").read_text("utf-8"))
    manifest["format_version"] = 2
    (export_dir / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    assert cause_of(export_dir) == "format_version_unsupported"


def test_a_missing_file(export_dir: Path):
    (export_dir / "festivals.jsonl").unlink()
    assert cause_of(export_dir) == "file_missing"


def test_a_row_count_that_disagrees_with_the_manifest(export_dir: Path):
    manifest = json.loads((export_dir / "manifest.json").read_text("utf-8"))
    manifest["files"]["places.jsonl"]["rows"] = 41
    (export_dir / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    assert cause_of(export_dir) == "row_count_mismatch"


def test_a_column_the_contract_does_not_name_stops_the_read(export_dir: Path):
    def add_phone(rows):
        rows[0]["tel"] = "02-000-0000"

    rewrite(export_dir, "places.jsonl", add_phone)

    with pytest.raises(ExportError) as caught:
        read_export(export_dir)
    assert caught.value.cause == "unexpected_column"
    assert "tel" in caught.value.detail
    # The column is named; its value is not repeated into a log.
    assert "02-000-0000" not in str(caught.value)


@pytest.mark.parametrize(
    "change",
    [
        lambda rows: rows[0].pop("name"),
        lambda rows: rows[0].update(id="101"),
        lambda rows: rows[0].update(lat=True),
        lambda rows: rows[0].update(has_congestion_data=None),
    ],
    ids=["required missing", "id as text", "bool where a number belongs", "required null"],
)
def test_a_row_of_the_wrong_shape(export_dir: Path, change):
    rewrite(export_dir, "places.jsonl", lambda rows: change(rows))
    assert cause_of(export_dir) == "row_invalid"


def test_the_same_place_twice(export_dir: Path):
    rewrite(export_dir, "places.jsonl", lambda rows: rows + [rows[0]])
    assert cause_of(export_dir) == "duplicate_id"


def test_a_link_to_a_place_that_was_not_exported(export_dir: Path):
    rewrite(export_dir, "related.jsonl", lambda rows: rows[0].update(related_id=99999))
    assert cause_of(export_dir) == "dangling_reference"


def test_an_event_that_ends_before_it_starts(export_dir: Path):
    rewrite(export_dir, "festivals.jsonl", lambda rows: rows[0].update(end_date="2026-01-01"))
    assert cause_of(export_dir) == "row_invalid"


def test_an_exhibition_at_a_place_outside_the_export_keeps_its_text(export_dir: Path):
    rewrite(export_dir, "exhibitions.jsonl", lambda rows: rows[0].update(attraction_id=99999))

    event = next(e for e in read_export(export_dir).events if e.id == "exhibition:old-maps")

    assert event.place_id is None
    assert event.place_text == "가람 역사박물관"
