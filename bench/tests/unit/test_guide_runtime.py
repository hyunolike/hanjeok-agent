from __future__ import annotations

from threading import Lock
from types import SimpleNamespace

import pytest

from guide.api import EnvRuntime
from guide.embeddings import compatible
from guide.graph.read import Active


@pytest.mark.parametrize(
    "place,wiki",
    [
        (None, None),
        ("other@1024", "expected@1024"),
        ("expected@1024", "expected@1024:old-preprocessing"),
        ("expected@1024", None),
    ],
)
def test_external_runtime_refuses_missing_or_mixed_embedding_identities(monkeypatch, place, wiki):
    class Driver:
        def session(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, *args, **kwargs):
            return SimpleNamespace(single=lambda: {"at": "now", "embedding_model": wiki})

    runtime = object.__new__(EnvRuntime)
    runtime._driver = Driver()
    runtime._embedder = SimpleNamespace(model_id="expected@1024", requires_identity=True)
    runtime._gazetteers = {}
    runtime._snapshot_lock = Lock()
    active = Active("g", "now", "sha", {}, embedding_model=place)
    monkeypatch.setattr("guide.graph.read.active", lambda _: active)
    monkeypatch.setattr(
        "guide.graph.read.gazetteer",
        lambda *args: pytest.fail("do not load names for an incompatible corpus"),
    )
    assert runtime.snapshot() is None


def test_only_legacy_local_mode_accepts_unmarked_vectors():
    local = SimpleNamespace(model_id="local@revision")
    remote = SimpleNamespace(model_id="remote@1024", requires_identity=True)
    assert compatible(local, None, None)
    assert not compatible(local, "remote@1024", None)
    assert not compatible(remote, None, None)
    assert compatible(remote, "remote@1024", "remote@1024")


def test_database_connection_pool_and_network_waits_are_bounded(monkeypatch):
    from bench.graph.store import driver_from_env

    monkeypatch.setattr("bench.graph.store.GraphDatabase.driver", lambda uri, **kw: kw)
    config = driver_from_env()
    assert config["max_connection_pool_size"] == 4
    assert config["connection_timeout"] == 5
    assert config["connection_acquisition_timeout"] == 5


def test_api_checkpoint_reset_clears_orphans_without_changing_default_saver(tmp_path, monkeypatch):
    from langgraph.checkpoint.base import empty_checkpoint

    from guide.api import checkpointer_from_env

    monkeypatch.setenv("GUIDE_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite"))
    saver = checkpointer_from_env()
    saver.put(
        {"configurable": {"thread_id": "orphan", "checkpoint_ns": ""}},
        empty_checkpoint(),
        {"source": "input", "step": 0, "parents": {}},
        {},
    )
    saver.conn.close()
    saver = checkpointer_from_env()
    assert list(saver.list(None))
    saver.conn.close()
    saver = checkpointer_from_env(reset=True)
    assert list(saver.list(None)) == []
    saver.conn.close()


@pytest.mark.parametrize("operation", ["ask", "context"])
def test_bench_rejects_incompatible_vectors_before_retrieval(monkeypatch, operation):
    from bench.runtime import BenchError, BenchRuntime

    class Driver:
        def session(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, *args, **kwargs):
            return SimpleNamespace(single=lambda: {"embedding_model": "local@revision"})

    monkeypatch.setattr("bench.runtime.corpus_snapshot", lambda *args: ("rev", "generation"))
    monkeypatch.setattr("bench.runtime.document_paths", lambda *args: {"a.md"})
    remote = SimpleNamespace(model_id="remote@1024", requires_identity=True)
    runtime = BenchRuntime(Driver(), remote, SimpleNamespace())
    with pytest.raises(BenchError, match="embedding"):
        if operation == "ask":
            runtime.ask("question", "wiki", "graph")
        else:
            runtime.corpus_context("wiki")
