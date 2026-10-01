"""Neo4j connection, schema and the corpus record.

Everything this module writes is derived from files and may be dropped at any
time — `rebuild` exists to prove it, and SC-007 checks that a rebuild reproduces
retrieval. Nothing lives here that cannot be regenerated, which is why the
corpus record holds a revision string and not, say, the loader's output.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from neo4j import Driver, GraphDatabase

# The vector index needs a width at creation time, so it is fixed here rather
# than inferred from whatever the first embedding happens to be — inferring it
# would let a model swap silently create a second, incompatible index.
EMBEDDING_DIM = 1024
VECTOR_INDEX = "chunk_embedding"


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    name: str
    revision: str
    docs: int
    chunks: int
    loaded_at: str


def driver_from_env() -> Driver:
    uri = os.environ.get("BENCH_NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("BENCH_NEO4J_USER", "neo4j")
    password = os.environ.get("BENCH_NEO4J_PASSWORD", "benchbench")
    return GraphDatabase.driver(uri, auth=(user, password))


@contextmanager
def session(driver: Driver):
    with driver.session() as s:
        yield s


SCHEMA = [
    # `(corpus, path)` is a document's identity. Without the constraint, a
    # second load would quietly create duplicate nodes and every count in every
    # report would be wrong in a way nothing would flag.
    "CREATE CONSTRAINT doc_identity IF NOT EXISTS "
    "FOR (d:Doc) REQUIRE (d.corpus, d.path) IS UNIQUE",
    "CREATE CONSTRAINT chunk_identity IF NOT EXISTS "
    "FOR (c:Chunk) REQUIRE (c.corpus, c.id) IS UNIQUE",
    "CREATE CONSTRAINT tag_identity IF NOT EXISTS "
    "FOR (t:Tag) REQUIRE (t.corpus, t.name) IS UNIQUE",
    "CREATE CONSTRAINT source_identity IF NOT EXISTS "
    "FOR (s:Source) REQUIRE (s.corpus, s.path) IS UNIQUE",
    "CREATE CONSTRAINT corpus_identity IF NOT EXISTS "
    "FOR (c:Corpus) REQUIRE c.name IS UNIQUE",
    # Citation validation hits this on every cited path of every answer.
    "CREATE INDEX doc_path IF NOT EXISTS FOR (d:Doc) ON (d.path)",
]


def ensure_schema(driver: Driver) -> None:
    with session(driver) as s:
        for statement in SCHEMA:
            s.run(statement)
        s.run(
            f"""
            CREATE VECTOR INDEX {VECTOR_INDEX} IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {{ indexConfig: {{
                `vector.dimensions`: $dim,
                `vector.similarity_function`: 'cosine'
            }} }}
            """,
            dim=EMBEDDING_DIM,
        )


def drop_corpus(driver: Driver, corpus: str) -> None:
    """Remove one corpus entirely, leaving others untouched.

    Deleting in batches rather than one transaction: a corpus of a few hundred
    documents is small, but `DETACH DELETE` over everything at once is the kind
    of statement that works until the day it does not.
    """
    with session(driver) as s:
        for label in ("Chunk", "Doc", "Tag", "Source"):
            while True:
                summary = s.run(
                    f"MATCH (n:{label} {{corpus: $corpus}}) "
                    "WITH n LIMIT 5000 DETACH DELETE n RETURN count(n) AS n",
                    corpus=corpus,
                ).single()
                if not summary or summary["n"] == 0:
                    break
        s.run("MATCH (c:Corpus {name: $corpus}) DETACH DELETE c", corpus=corpus)


def record_corpus(driver: Driver, name: str, revision: str, docs: int, chunks: int) -> CorpusRecord:
    loaded_at = datetime.now(UTC).isoformat()
    with session(driver) as s:
        s.run(
            "MERGE (c:Corpus {name: $name}) "
            "SET c.revision = $revision, c.docs = $docs, c.chunks = $chunks, "
            "    c.loaded_at = $loaded_at",
            name=name,
            revision=revision,
            docs=docs,
            chunks=chunks,
            loaded_at=loaded_at,
        )
    return CorpusRecord(name, revision, docs, chunks, loaded_at)


def corpora(driver: Driver) -> list[CorpusRecord]:
    with session(driver) as s:
        rows = s.run(
            "MATCH (c:Corpus) RETURN c.name AS name, c.revision AS revision, "
            "c.docs AS docs, c.chunks AS chunks, c.loaded_at AS loaded_at "
            "ORDER BY c.name"
        )
        return [CorpusRecord(**dict(row)) for row in rows]


def corpus_revision(driver: Driver, name: str) -> str | None:
    """The revision every run against this corpus is stamped with. `None` means
    the corpus is not loaded, which callers must treat as a 409 rather than
    answering from whatever else is in the database."""
    with session(driver) as s:
        row = s.run(
            "MATCH (c:Corpus {name: $name}) RETURN c.revision AS revision", name=name
        ).single()
        return row["revision"] if row else None
