import json

import pytest

from bench.answer.pipeline import AnswerPipeline
from bench.corpus.loader import LoadedDoc
from bench.graph.build import build
from bench.graph.store import driver_from_env, drop_corpus, ensure_schema, record_corpus

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(embedder):
    driver = driver_from_env()
    ensure_schema(driver)
    for corpus in ("whole-test", "whole-foreign"):
        drop_corpus(driver, corpus)
    docs = [
        LoadedDoc(
            "z.md",
            "whole-test",
            "Z",
            "note",
            "# First\nfirst fact\n## Second\n" + "full " * 300,
            attrs={"unfamiliar": {"value": "preserve"}},
        ),
        LoadedDoc("a.md", "whole-test", "A", "note", "alpha fact"),
    ]
    counts = build(driver, docs, embedder)
    record_corpus(driver, "whole-test", "rev", counts.docs, counts.chunks)
    build(driver, [LoadedDoc("foreign.md", "whole-foreign", "F", "note", "never supply")], embedder)
    yield driver
    for corpus in ("whole-test", "whole-foreign"):
        drop_corpus(driver, corpus)
    driver.close()


def test_whole_supplies_all_chunks_in_stable_order_without_embeddings(graph):
    from bench.answer.strategies import WholeStrategy

    rows = WholeStrategy(graph)("whole-test", "arbitrary question")
    assert [p.chunk for p in rows] == ["a.md#0", "z.md#0", "z.md#1"]
    assert rows[-1].text.endswith("full " * 299 + "full")
    assert rows[-1].attrs == {"unfamiliar": {"value": "preserve"}}
    assert rows[-1].heading_path == ("First", "Second")
    assert not any(p.expanded for p in rows)


def test_whole_runtime_uses_the_same_pipeline_and_supports_http(graph, embedder, scripted):
    from fastapi.testclient import TestClient

    from bench.api import create_app
    from bench.runtime import BenchRuntime

    class NoQueryEmbedding:
        def embed_query(self, question):
            raise AssertionError("whole must not embed the query")

    model = scripted(
        json.dumps({"outcome": "answered", "answer": "alpha fact", "citations": ["a.md"]})
    )
    runtime = BenchRuntime(graph, NoQueryEmbedding(), model)
    response = TestClient(create_app(runtime)).post(
        "/bench/ask", json={"question": "What?", "corpus": "whole-test", "strategy": "whole"}
    )
    assert response.status_code == 200
    assert response.json()["answer"] == "alpha fact"
    assert len(response.json()["supplied"]) == 3


def test_whole_uses_shared_citation_gate(graph, scripted):
    from bench.answer.strategies import WholeStrategy

    bad = '{"outcome":"answered","answer":"discard this","citations":["foreign.md"]}'
    result = AnswerPipeline(WholeStrategy(graph), scripted(bad, bad)).ask(
        "What?", "whole-test", "rev", {"a.md", "z.md"}
    )
    assert result.outcome == "invalid_citations" and result.repair_count == 1
    assert result.answer is None and not result.citations
