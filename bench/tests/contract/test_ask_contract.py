import json

import pytest
from fastapi.testclient import TestClient

from bench.graph.query import Passage


class TestRuntime:
    """Only the external database boundary is replaced, not answer validation."""

    __test__ = False

    def __init__(self, model):
        self.model = model
        self.seen = []

    def ask(self, question, corpus, strategy):
        from bench.answer.pipeline import AnswerPipeline
        from bench.runtime import BenchError

        self.seen.append((question, corpus, strategy))
        if corpus == "absent":
            raise BenchError("load_failed", "corpus is not loaded", 409)
        if corpus == "broken":
            raise BenchError("load_failed", "graph unavailable", 503)
        rows = [Passage("a.md", "a.md#0", "supported text", "A")]
        if strategy == "whole":
            rows.append(Passage("b.md", "b.md#0", "additional text", "B"))
        pipeline = AnswerPipeline(
            lambda c, q: rows,
            self.model,
        )
        return pipeline.ask(question, corpus, "test-revision", {"a.md", "b.md"})

    def list_corpora(self):
        return [
            {
                "name": "test",
                "revision": "test-revision",
                "docs": 1,
                "chunks": 1,
                "loaded_at": "2026-10-11T00:00:00Z",
            }
        ]

    def rebuild(self, name):
        if name != "test":
            from bench.runtime import BenchError

            raise BenchError("load_failed", "corpus loader is not configured", 409)
        return {
            "name": name,
            "revision": "new-revision",
            "docs": 1,
            "chunks": 1,
            "dropped": [{"source_path": "a.md", "target": "missing", "kind": "link"}],
        }


def client(scripted, *replies):
    from bench.api import create_app

    runtime = TestRuntime(scripted(*replies))
    return TestClient(create_app(runtime)), runtime


def post(c, **overrides):
    return c.post(
        "/bench/ask",
        json={"question": "What is A?", "corpus": "test", "strategy": "graph", **overrides},
    )


def test_answer_contains_revision_supplied_passages_and_usage(scripted):
    c, _ = client(scripted, '{"outcome":"answered","answer":"supported text","citations":["a.md"]}')
    response = post(c)
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "supported text"
    assert body["corpus_revision"] == "test-revision"
    assert body["supplied"] == [{"doc": "a.md", "chunk": "a.md#0", "chars": 14}]
    assert set(body["usage"]) == {"prompt_tokens", "completion_tokens", "elapsed_ms"}


def test_no_grounds_has_null_answer(scripted):
    c, _ = client(scripted, '{"outcome":"no_grounds","answer":null,"citations":[]}')
    response = post(c)
    assert response.status_code == 200
    assert response.json()["answer"] is None
    assert response.json()["outcome"] == "no_grounds"


def test_invalid_citations_never_ship_rejected_text_or_paths(scripted):
    invalid = json.dumps(
        {
            "outcome": "answered",
            "answer": "private rejected text",
            "citations": ["/outside/secret.md"],
        }
    )
    c, _ = client(scripted, invalid, invalid)
    response = post(c)
    assert response.status_code == 422
    assert response.json()["outcome"] == "invalid_citations"
    assert "answer" not in response.json()
    assert "private rejected" not in response.text
    assert "/outside" not in response.text


@pytest.mark.parametrize("corpus,status", [("absent", 409), ("broken", 503)])
def test_graph_failures_are_distinct(scripted, corpus, status):
    c, _ = client(scripted)
    response = post(c, corpus=corpus)
    assert response.status_code == status
    assert response.json()["outcome"] == "load_failed"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": "x", "corpus": "test"},
        {"question": "x", "strategy": "graph"},
        {"question": " "},
        {"question": "x" * 2001},
        {"strategy": "unknown"},
        {"corpus": " "},
    ],
)
def test_bad_input_is_rejected_before_runtime_and_never_echoed(scripted, body):
    c, runtime = client(scripted)
    response = c.post("/bench/ask", json=body)
    assert response.status_code == 422
    assert runtime.seen == []
    assert "input" not in response.text
    assert response.json()["outcome"] == "load_failed"


def test_whole_is_not_silently_replaced_with_graph(scripted):
    c, _ = client(scripted, '{"outcome":"answered","answer":"supported text","citations":["a.md"]}')
    response = post(c, strategy="whole")
    assert response.status_code == 200
    assert {p["doc"] for p in response.json()["supplied"]} == {"a.md", "b.md"}


def test_discovery_and_rebuild_report_dropped_refs(scripted):
    c, _ = client(scripted)
    assert c.get("/bench/corpora").json()[0]["name"] == "test"
    response = c.post("/bench/corpora/test/rebuild")
    assert response.status_code == 200
    assert response.json()["dropped"][0]["target"] == "missing"


def test_model_failure_has_503_and_no_answer(scripted):
    c, _ = client(scripted, "bad output")
    response = post(c)
    assert response.status_code == 503
    assert response.json()["outcome"] == "model_failed"
    assert "answer" not in response.json()
