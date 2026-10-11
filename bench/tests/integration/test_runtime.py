import json

import pytest
from fastapi.testclient import TestClient

from bench.corpus.loader import DroppedRef, LoadedDoc, LoadResult
from bench.graph.store import corpus_revision, driver_from_env, drop_corpus

pytestmark = pytest.mark.integration


class Loader:
    name = "runtime-test"

    def __init__(self):
        self.docs = (
            LoadedDoc("a.md", self.name, "Alpha", "synthetic", "alpha fact", links=("b.md",)),
            LoadedDoc("b.md", self.name, "Beta", "synthetic", "beta fact"),
        )

    def load(self):
        return LoadResult(self.docs, (DroppedRef("a.md", "missing.md", "link"),), "rev-1")


@pytest.fixture
def runtime(embedder, scripted):
    from bench.runtime import BenchRuntime

    driver, loader = driver_from_env(), Loader()
    drop_corpus(driver, loader.name)
    model = scripted(
        json.dumps({"outcome": "answered", "answer": "alpha fact", "citations": ["a.md"]})
    )
    service = BenchRuntime(driver, embedder, model, {loader.name: loader})
    yield service, loader, model
    drop_corpus(driver, loader.name)
    service.close()


def test_actual_load_query_answer_and_http_discovery(runtime):
    from bench.api import create_app

    service, loader, _ = runtime
    counts = service.rebuild(loader.name)
    assert counts["docs"] == 2 and counts["dropped"][0]["target"] == "missing.md"
    c = TestClient(create_app(service))
    response = c.post(
        "/bench/ask", json={"question": "alpha fact", "corpus": loader.name, "strategy": "graph"}
    )
    assert response.status_code == 200
    assert response.json()["answer"] == "alpha fact"
    assert response.json()["corpus_revision"] == "rev-1"
    assert {p["doc"] for p in response.json()["supplied"]} == {"a.md", "b.md"}
    assert any(row["name"] == loader.name for row in c.get("/bench/corpora").json())


def test_rebuild_removes_obsolete_documents_and_edges(runtime):
    from bench.graph.query import document_paths, expand, vector_search

    service, loader, _ = runtime
    service.rebuild(loader.name)
    loader.docs = (LoadedDoc("a.md", loader.name, "Alpha", "synthetic", "alpha fact"),)
    service.rebuild(loader.name)
    assert document_paths(service.driver, loader.name) == {"a.md"}
    seeds = vector_search(service.driver, loader.name, service.embedder.embed_query("alpha fact"))
    assert expand(service.driver, loader.name, seeds) == []


def test_empty_or_mixed_loader_does_not_erase_existing_corpus(runtime):
    from bench.runtime import BenchError

    service, loader, _ = runtime
    service.rebuild(loader.name)
    for docs in [(), (LoadedDoc("bad.md", "foreign", "Bad", "note", "bad"),)]:
        loader.docs = docs
        with pytest.raises(BenchError, match="rebuild failed"):
            service.rebuild(loader.name)
        assert corpus_revision(service.driver, loader.name) == "rev-1"


def test_missing_corpus_does_not_call_model(runtime):
    from bench.runtime import BenchError

    service, _, model = runtime
    with pytest.raises(BenchError) as error:
        service.ask("question", "not-loaded", "graph")
    assert error.value.status == 409
    assert model.calls == []


def test_same_revision_rebuild_during_a_question_is_detected(runtime, monkeypatch):
    from bench.answer.strategies import GraphStrategy
    from bench.runtime import BenchError, BenchRuntime

    service, loader, _ = runtime
    service.rebuild(loader.name)
    other = BenchRuntime(service.driver, service.embedder, service.model, {loader.name: loader})
    select = GraphStrategy.__call__

    def interleaved(strategy, corpus, question):
        passages = select(strategy, corpus, question)
        other.rebuild(loader.name)
        return passages

    monkeypatch.setattr(GraphStrategy, "__call__", interleaved)
    with pytest.raises(BenchError) as error:
        service.ask("alpha fact", loader.name, "graph")
    assert error.value.status == 409
    assert error.value.cause == "corpus changed during the request"


def test_corpus_is_invalidated_before_any_chunks_are_deleted(runtime, monkeypatch):
    from bench.graph.store import session

    service, loader, _ = runtime
    service.rebuild(loader.name)
    from bench.graph import store

    real_session = store.session
    observations = []

    class SessionSpy:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def run(self, statement, **kwargs):
            if "n:Chunk" in statement and "DELETE" in statement:
                with session(service.driver) as s:
                    row = s.run(
                        "MATCH (c:Corpus {name: $name}) RETURN count(c) AS n", name=loader.name
                    ).single()
                    observations.append(row["n"])
            return self.wrapped.run(statement, **kwargs)

    from contextlib import contextmanager

    @contextmanager
    def spying_session(driver):
        with real_session(driver) as s:
            yield SessionSpy(s)

    monkeypatch.setattr(store, "session", spying_session)
    store.drop_corpus(service.driver, loader.name)
    assert observations and all(n == 0 for n in observations)


def test_rebuild_diagnostics_do_not_echo_outside_corpus_paths(runtime):
    service, loader, _ = runtime
    original = loader.load()
    loader.load = lambda: LoadResult(
        original.docs,
        (
            DroppedRef("a.md", "/Users/private/missing.md", "source"),
            DroppedRef("a.md", "../outside.md", "source"),
            DroppedRef("a.md", "safe/missing.md", "source"),
        ),
        "r",
    )
    result = service.rebuild(loader.name)
    text = json.dumps(result)
    assert "/Users/private" not in text and "../outside" not in text
    assert result["dropped"][2]["target"] == "safe/missing.md"
