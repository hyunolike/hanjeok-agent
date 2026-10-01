"""Graph build against a real Neo4j. Marked `integration`; not in the default run."""

from __future__ import annotations

import pytest

from bench.corpus.loader import LoadedDoc
from bench.graph.build import build
from bench.graph.store import (
    corpora,
    corpus_revision,
    driver_from_env,
    drop_corpus,
    ensure_schema,
    record_corpus,
    session,
)

pytestmark = pytest.mark.integration

CORPUS = "itest"


@pytest.fixture
def driver():
    d = driver_from_env()
    ensure_schema(d)
    drop_corpus(d, CORPUS)
    yield d
    drop_corpus(d, CORPUS)
    d.close()


@pytest.fixture
def docs() -> list[LoadedDoc]:
    return [
        LoadedDoc(
            path="concepts/a.md",
            corpus=CORPUS,
            title="A",
            doc_type="concept",
            body="# A\n\nAlpha text.\n\n## Detail\n\nMore alpha.",
            tags=("shared", "only-a"),
            links=("concepts/b.md",),
            sources=("raw/one.md",),
            attrs={"confidence": "high", "conflicts": ["a says X, b says Y"]},
        ),
        LoadedDoc(
            path="concepts/b.md",
            corpus=CORPUS,
            title="B",
            doc_type="concept",
            body="# B\n\nBeta text.",
            tags=("shared",),
            sources=("raw/one.md",),
            attrs={"confidence": "low"},
        ),
    ]


def test_build_writes_nodes_and_edges(driver, docs, embedder):
    counts = build(driver, docs, embedder)

    assert counts.docs == 2
    assert counts.chunks == 3  # A splits at its heading; B stays whole
    assert counts.tags == 2
    assert counts.sources == 1  # both cite the same raw file
    assert counts.links == 1

    with session(driver) as s:
        row = s.run(
            "MATCH (d:Doc {corpus: $c})-[:HAS_CHUNK]->(ch:Chunk) "
            "RETURN count(DISTINCT d) AS docs, count(ch) AS chunks",
            c=CORPUS,
        ).single()
        assert row["docs"] == 2
        assert row["chunks"] == 3


def test_shared_source_puts_two_documents_one_hop_apart(driver, docs, embedder):
    # This is the edge that makes the graph arm more than vector search: two
    # pages that drew on the same evidence are reachable from each other.
    build(driver, docs, embedder)

    with session(driver) as s:
        row = s.run(
            "MATCH (a:Doc {corpus: $c, path: 'concepts/a.md'})-[:CITES]->(:Source)"
            "<-[:CITES]-(b:Doc) RETURN b.path AS path",
            c=CORPUS,
        ).single()
        assert row["path"] == "concepts/b.md"


def test_attrs_are_stored_whole_and_not_as_named_properties(driver, docs, embedder):
    # Principle III at the storage layer: the builder serialises attrs without
    # naming a key, so `confidence` must not exist as its own property.
    build(driver, docs, embedder)

    with session(driver) as s:
        row = s.run(
            "MATCH (d:Doc {corpus: $c, path: 'concepts/a.md'}) RETURN properties(d) AS p",
            c=CORPUS,
        ).single()
        props = row["p"]

    assert "attrs_json" in props
    assert "confidence" not in props
    assert "conflicts" not in props


def test_building_twice_does_not_duplicate(driver, docs, embedder):
    # The uniqueness constraints are the guard, but a second load is the real
    # thing that would hit them, and a duplicated corpus would make every count
    # in every report wrong without raising anything.
    build(driver, docs, embedder)
    build(driver, docs, embedder)

    with session(driver) as s:
        row = s.run(
            "MATCH (d:Doc {corpus: $c}) RETURN count(d) AS n", c=CORPUS
        ).single()
        assert row["n"] == 2


def test_drop_removes_one_corpus_and_leaves_others(driver, docs, embedder):
    build(driver, docs, embedder)
    other = [
        LoadedDoc(path="x.md", corpus="itest-other", title="X", doc_type="t", body="# X\n\nx")
    ]
    build(driver, other, embedder)

    drop_corpus(driver, CORPUS)

    with session(driver) as s:
        gone = s.run("MATCH (d:Doc {corpus: $c}) RETURN count(d) AS n", c=CORPUS).single()
        kept = s.run(
            "MATCH (d:Doc {corpus: 'itest-other'}) RETURN count(d) AS n"
        ).single()
        assert gone["n"] == 0
        assert kept["n"] == 1

    drop_corpus(driver, "itest-other")


def test_corpus_record_carries_the_revision(driver, docs, embedder):
    # Every run is stamped with this, and the pair validity rule compares it.
    counts = build(driver, docs, embedder)
    record_corpus(driver, CORPUS, "abc1234", counts.docs, counts.chunks)

    assert corpus_revision(driver, CORPUS) == "abc1234"
    assert any(c.name == CORPUS and c.docs == 2 for c in corpora(driver))


def test_unloaded_corpus_has_no_revision(driver):
    # Callers must turn this into a 409 rather than answering from whatever
    # else happens to be in the database.
    assert corpus_revision(driver, "never-loaded") is None
