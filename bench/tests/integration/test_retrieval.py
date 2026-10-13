"""Query the actual Neo4j store: isolation, graph expansion and reproducibility."""

import pytest

from bench.corpus.loader import LoadedDoc
from bench.graph.build import build
from bench.graph.store import driver_from_env, drop_corpus, ensure_schema

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(embedder):
    driver = driver_from_env()
    ensure_schema(driver)
    for name in ("query-test", "query-other"):
        drop_corpus(driver, name)
    docs = [
        LoadedDoc(
            "a.md",
            "query-test",
            "Alpha",
            "note",
            "alpha seed text",
            links=("b.md",),
            tags=("shared",),
            sources=("raw/x.md",),
            attrs={"unknown": ["preserve me"]},
        ),
        LoadedDoc("b.md", "query-test", "Beta", "note", "Linked evidence.\n" + "z" * 900),
        LoadedDoc("c.md", "query-test", "Gamma", "note", "Shared tag evidence.", tags=("shared",)),
        LoadedDoc(
            "d.md", "query-test", "Delta", "note", "Shared source evidence.", sources=("raw/x.md",)
        ),
        LoadedDoc("e.md", "query-test", "Epsilon", "note", "second hop only", links=("b.md",)),
    ]
    build(driver, docs, embedder)
    build(
        driver,
        [LoadedDoc("foreign.md", "query-other", "Other", "note", "alpha seed text")],
        embedder,
    )
    yield driver, docs
    for name in ("query-test", "query-other"):
        drop_corpus(driver, name)
    driver.close()


def test_top_k_is_scoped_before_ranking_and_attrs_survive(graph, embedder):
    from bench.graph.query import vector_search

    driver, _ = graph
    hits = vector_search(
        driver, "query-test", embedder.embed(["alpha seed text"])[0], k=1, min_score=0.9
    )
    assert [(p.doc, p.chunk) for p in hits] == [("a.md", "a.md#0")]
    assert hits[0].attrs == {"unknown": ["preserve me"]}
    assert hits[0].text == "alpha seed text"


def test_expansion_is_one_hop_bounded_and_deduplicated(graph, embedder):
    from bench.graph.query import expand, vector_search

    driver, _ = graph
    seeds = vector_search(driver, "query-test", embedder.embed(["alpha seed text"])[0], k=1)
    widened = expand(driver, "query-test", seeds, limit=8)
    assert [p.doc for p in widened] == ["b.md", "c.md", "d.md"]
    assert widened[0].text == "Linked evidence."
    assert all(len(p.text) <= 240 and p.expanded for p in widened)


def test_empty_seeds_do_not_expand_to_the_whole_corpus(graph):
    from bench.graph.query import expand

    assert expand(graph[0], "query-test", []) == []


def test_rebuild_reproduces_passage_order(graph, embedder):
    from bench.graph.query import vector_search

    driver, docs = graph
    vector = embedder.embed(["alpha"])[0]
    before = [(p.doc, p.chunk) for p in vector_search(driver, "query-test", vector)]
    drop_corpus(driver, "query-test")
    build(driver, docs, embedder)
    after = [(p.doc, p.chunk) for p in vector_search(driver, "query-test", vector)]
    assert before == after


def test_no_score_above_threshold_returns_no_passages(graph, embedder):
    from bench.graph.query import vector_search

    assert (
        vector_search(graph[0], "query-test", embedder.embed(["unrelated"])[0], min_score=0.99)
        == []
    )
