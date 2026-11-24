"""The snapshot adapter reads a real file; only hosted embedding is replaced."""

from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3

import pytest

from bench.corpus.loader import LoadedDoc, LoadResult
from guide.export import Event, Export, Place, Related

MODEL = "fixture@1024:v1"


def unit(axis):
    return [float(i == axis) for i in range(1024)]


class Embedder:
    model_id = MODEL
    requires_identity = True

    def embed_query(self, text):
        return unit(0)


def api():
    try:
        return importlib.import_module("guide.sqlite_store")
    except ModuleNotFoundError:
        pytest.fail("SQLite snapshot store has not been implemented")


def data():
    def place(id, name, region, covered=True):
        return Place(
            id, name, region, region, None, None, None, None, "소개", "주소", 37.5, 127.0, covered
        )

    export = Export(
        "2026-11-23T00:00:00Z",
        "public",
        "a" * 64,
        (place(1, "가람궁", "A"), place(2, "가람 궁원", "B"), place(3, "은행나무길", "A", False)),
        (Related(1, 3, None, 0.99, 1, 2), Related(1, 2, 1, 0.1, 2, 3)),
        (
            Event("festival:1", "festival", "가까운 행사", "2026-11-01", "2026-11-30", 37.5, 127.0),
            Event(
                "exhibition:2",
                "exhibition",
                "다른 장소 행사",
                "2026-11-01",
                "2026-11-30",
                37.5,
                127.0,
                place_id=2,
            ),
            Event("festival:3", "festival", "먼 행사", "2026-11-01", "2026-11-30", 38.0, 127.0),
        ),
    )
    wiki = LoadResult(
        (
            LoadedDoc(
                path="concepts/a.md",
                corpus="wiki",
                title="가",
                doc_type="concept",
                body="# 첫째\n본문\n# 둘째\n다음",
            ),
            LoadedDoc(
                path="concepts/b.md",
                corpus="wiki",
                title="나",
                doc_type="concept",
                body="다른 본문",
            ),
        ),
        (),
        revision="abc1234",
    )
    return export, wiki


def prepare(tmp_path, *, vectors=None):
    module = api()
    export, wiki = data()
    path = tmp_path / "snapshot.sqlite"
    provenance = {
        "embedding_model": MODEL,
        "wiki_embedding_model": MODEL,
        "wiki_revision": "abc1234",
        "wiki_as_of": "2026-11-23",
        "wiki_embedding_producer": "fixture",
        "wiki_artifact_sha256": "b" * 64,
    }
    manifest = module.write_snapshot(
        path,
        export,
        wiki,
        vectors or {1: unit(0), 2: unit(0), 3: unit(1)},
        {"concepts/a.md#0": unit(0), "concepts/a.md#1": unit(0), "concepts/b.md#0": unit(1)},
        provenance,
    )
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest))
    return path, mp


def test_sqlite_search_filters_region_before_limit_and_breaks_ties_by_id(tmp_path):
    path, manifest = prepare(tmp_path)
    with api().SQLiteStore(path, manifest, Embedder()) as store:
        assert [p.id for p in store.places.search("궁", limit=1, region_code="B")] == [2]
        assert [p.id for p in store.places.search("궁", limit=2, region_code=None)] == [1, 2]
        assert store.places.search("궁", limit=2, region_code="missing") == []


def test_sqlite_names_related_order_missing_detail_and_gazetteer(tmp_path):
    path, manifest = prepare(tmp_path)
    with api().SQLiteStore(path, manifest, Embedder()) as store:
        assert [p.id for p in store.places.match_name("가람궁")] == [1, 2]
        assert store.places.match_name("   ") == []
        assert store.places.detail(999) is None
        assert store.places.detail(1).name == "가람궁"
        assert [(r.rank, r.place.id) for r in store.places.related(1, limit=10)] == [
            (1, 2),
            (None, 3),
        ]
        assert store.places.gazetteer()["은행나무길"][0].covered is False


def test_sqlite_events_respect_dates_and_do_not_reassign_tied_events(tmp_path):
    path, manifest = prepare(tmp_path)
    with api().SQLiteStore(path, manifest, Embedder()) as store:
        assert [e.id for e in store.places.events(1, on="2026-11-24")] == ["festival:1"]
        assert store.places.events(1, on="2026-12-01") == []
        assert [e.id for e in store.places.events(2, on="2026-11-24")] == [
            "exhibition:2",
            "festival:1",
        ]


def test_sqlite_wiki_returns_best_chunk_pages_once_and_keeps_original_text(tmp_path):
    path, manifest = prepare(tmp_path)
    with api().SQLiteStore(path, manifest, Embedder()) as store:
        assert [p.path for p in store.policy.search("정책", limit=2)] == [
            "concepts/a.md",
            "concepts/b.md",
        ]
        # GraphPolicy joins chunk bodies; the splitter stores headings separately.
        assert store.policy.page("concepts/a.md").text == "본문\n\n다음"
        assert store.policy.page("missing.md") is None
        assert store.meta["counts"] == {"places": 3, "related": 2, "events": 3, "regions": 2}


@pytest.mark.parametrize("bad", [[0.0] * 1024, [1.0], [float("nan")] * 1024])
def test_sqlite_writer_rejects_invalid_vectors_without_replacing_good_artifact(tmp_path, bad):
    path, _ = prepare(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="vector"):
        prepare(tmp_path, vectors={1: bad, 2: unit(0), 3: unit(1)})
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["hash", "identity", "count", "schema"])
def test_sqlite_refuses_tampered_or_incompatible_artifacts(tmp_path, change):
    path, mp = prepare(tmp_path)
    manifest = json.loads(mp.read_text())
    if change == "hash":
        path.write_bytes(path.read_bytes() + b"damaged")
    elif change == "identity":
        manifest["metadata"]["wiki_embedding_model"] = "other"
    else:
        with sqlite3.connect(path) as db:
            if change == "count":
                db.execute("DELETE FROM places WHERE id = 1")
            else:
                db.execute("PRAGMA user_version = 999")
        manifest["database_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    mp.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        api().SQLiteStore(path, mp, Embedder())


def test_sqlite_is_read_only_and_missing_file_is_never_created(tmp_path):
    path, manifest = prepare(tmp_path)
    with (
        api().SQLiteStore(path, manifest, Embedder()) as store,
        pytest.raises(sqlite3.OperationalError, match="readonly"),
    ):
        store._db.execute("DELETE FROM places")
    missing = tmp_path / "missing.sqlite"
    with pytest.raises((ValueError, OSError, sqlite3.Error)):
        api().SQLiteStore(missing, manifest, Embedder())
    assert not missing.exists()


def test_sqlite_policy_preserves_top_three_times_limit_chunk_window(tmp_path):
    from dataclasses import replace

    export, wiki = data()
    wiki = replace(
        wiki,
        docs=(
            replace(wiki.docs[0], body="\n".join(f"# 절{i}\n내용{i}" for i in range(7))),
            wiki.docs[1],
        ),
    )
    vectors = {f"concepts/a.md#{i}": unit(0) for i in range(7)}
    vectors["concepts/b.md#0"] = unit(1)
    path = tmp_path / "window.sqlite"
    meta = {"embedding_model": MODEL, "wiki_embedding_model": MODEL, "wiki_revision": "abc1234"}
    manifest = api().write_snapshot(
        path, export, wiki, {1: unit(0), 2: unit(0), 3: unit(1)}, vectors, meta
    )
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest))
    with api().SQLiteStore(path, mp, Embedder()) as store:
        assert [p.path for p in store.policy.search("정책", limit=2)] == ["concepts/a.md"]


def test_sqlite_runtime_serves_ready_without_neo4j_credentials(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from guide.api import create_app

    path, manifest = prepare(tmp_path)
    monkeypatch.setenv("GUIDE_STORE", "sqlite")
    monkeypatch.setenv("GUIDE_LIVE_MODE", "replay")
    monkeypatch.setenv("GUIDE_SNAPSHOT_DB", str(path))
    monkeypatch.setenv("GUIDE_SNAPSHOT_MANIFEST", str(manifest))
    monkeypatch.setenv("GUIDE_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setattr("guide.embeddings.embedder_from_env", Embedder)
    monkeypatch.setattr(
        "bench.graph.store.driver_from_env", lambda: pytest.fail("SQLite must not open Neo4j")
    )
    with TestClient(create_app()) as client:
        assert client.get("/guide/ready").status_code == 200
        assert client.get("/guide/status").json()["counts"]["places"] == 3


def test_sqlite_runtime_missing_file_returns_503_without_fallback(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from guide.api import create_app

    monkeypatch.setenv("GUIDE_STORE", "sqlite")
    monkeypatch.setenv("GUIDE_LIVE_MODE", "replay")
    monkeypatch.setenv("GUIDE_SNAPSHOT_DB", str(tmp_path / "missing.sqlite"))
    monkeypatch.setenv("GUIDE_SNAPSHOT_MANIFEST", str(tmp_path / "missing.json"))
    monkeypatch.setenv("GUIDE_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setattr("guide.embeddings.embedder_from_env", Embedder)
    monkeypatch.setattr("bench.graph.store.driver_from_env", lambda: pytest.fail("No fallback"))
    with TestClient(create_app()) as client:
        assert client.get("/guide/ready").status_code == 503
    assert not (tmp_path / "missing.sqlite").exists()


@pytest.mark.parametrize("bad_manifest", ["[]", "null", '{"metadata": []}'])
def test_sqlite_runtime_bad_json_shape_stays_up_but_unready(tmp_path, monkeypatch, bad_manifest):
    from fastapi.testclient import TestClient

    from guide.api import create_app

    path, manifest = prepare(tmp_path)
    manifest.write_text(bad_manifest)
    monkeypatch.setenv("GUIDE_STORE", "sqlite")
    monkeypatch.setenv("GUIDE_LIVE_MODE", "replay")
    monkeypatch.setenv("GUIDE_SNAPSHOT_DB", str(path))
    monkeypatch.setenv("GUIDE_SNAPSHOT_MANIFEST", str(manifest))
    monkeypatch.setenv("GUIDE_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setattr("guide.embeddings.embedder_from_env", Embedder)
    with TestClient(create_app()) as client:
        assert client.get("/guide/ready").status_code == 503


def test_sqlite_related_null_scores_sort_like_cypher_descending(tmp_path):
    from dataclasses import replace

    export, wiki = data()
    export = replace(
        export, related=(Related(1, 2, 1, 0.9, None, None), Related(1, 3, 1, None, None, None))
    )
    path = tmp_path / "null.sqlite"
    manifest = api().write_snapshot(
        path,
        export,
        wiki,
        {1: unit(0), 2: unit(0), 3: unit(1)},
        {"concepts/a.md#0": unit(0), "concepts/a.md#1": unit(0), "concepts/b.md#0": unit(1)},
        {"embedding_model": MODEL, "wiki_embedding_model": MODEL, "wiki_revision": "abc1234"},
    )
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest))
    with api().SQLiteStore(path, mp, Embedder()) as store:
        assert [r.place.id for r in store.places.related(1, limit=10)] == [3, 2]


def test_sqlite_event_just_outside_neo4j_one_km_boundary_is_excluded(tmp_path):
    from dataclasses import replace

    export, wiki = data()
    # A latitude delta of .00899 degrees is 1000.762m using Neo4j's radius,
    # but 999.644m using the mean radius. It must be outside the 1000m gate.
    export = replace(export, events=(replace(export.events[0], lat=37.50899),))
    path = tmp_path / "boundary.sqlite"
    manifest = api().write_snapshot(
        path,
        export,
        wiki,
        {1: unit(0), 2: unit(0), 3: unit(1)},
        {"concepts/a.md#0": unit(0), "concepts/a.md#1": unit(0), "concepts/b.md#0": unit(1)},
        {"embedding_model": MODEL, "wiki_embedding_model": MODEL, "wiki_revision": "abc1234"},
    )
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest))
    with api().SQLiteStore(path, mp, Embedder()) as store:
        assert store.places.events(1, on="2026-11-24") == []
