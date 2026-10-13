"""Turn a `LoadedDoc` stream into nodes and edges.

This module is the first one past the seam, so it is the one most likely to
break Principle III by reaching into `attrs` for a key it recognises. It must
not: `attrs` is copied onto the node as a whole and never inspected.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from neo4j import Driver

from bench.corpus.chunk import Chunk, split
from bench.corpus.loader import LoadedDoc
from bench.graph.store import session


class Embedder:
    """What `build` needs from an embedding model, and nothing more.

    A protocol rather than a concrete client so the unit suite can supply a
    deterministic fake — the constitution requires tests to pass with no network
    and no key, and an embedding call is the easiest way to break that.
    """

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


@dataclass(frozen=True, slots=True)
class BuildCounts:
    docs: int
    chunks: int
    tags: int
    sources: int
    links: int
    cites: int


def build(driver: Driver, docs: Iterable[LoadedDoc], embedder: Embedder) -> BuildCounts:
    docs = list(docs)
    if not docs:
        return BuildCounts(0, 0, 0, 0, 0, 0)

    corpus = docs[0].corpus

    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(split(doc.path, doc.body))

    # One batched call rather than one per chunk: the embedder may be a remote
    # model, and a loop here would turn a load into a few hundred round trips.
    vectors = embedder.embed([c.text for c in chunks]) if chunks else []
    if len(vectors) != len(chunks):
        raise ValueError(f"embedder returned {len(vectors)} vectors for {len(chunks)} chunks")

    with session(driver) as s:
        s.run(
            """
            UNWIND $docs AS doc
            MERGE (d:Doc {corpus: $corpus, path: doc.path})
            SET d.title = doc.title,
                d.doc_type = doc.doc_type,
                d.updated = doc.updated,
                // Serialised whole. Spreading it into properties would mean
                // naming its keys here, which is exactly what Principle III
                // forbids this module from knowing.
                d.attrs_json = doc.attrs_json
            """,
            corpus=corpus,
            docs=[
                {
                    "path": d.path,
                    "title": d.title,
                    "doc_type": d.doc_type,
                    "updated": d.updated.isoformat() if d.updated else None,
                    "attrs_json": json.dumps(dict(d.attrs), ensure_ascii=False, default=str),
                }
                for d in docs
            ],
        )

        s.run(
            """
            UNWIND $rows AS row
            MATCH (d:Doc {corpus: $corpus, path: row.doc})
            MERGE (t:Tag {corpus: $corpus, name: row.tag})
            MERGE (d)-[:TAGGED]->(t)
            """,
            corpus=corpus,
            rows=[{"doc": d.path, "tag": t} for d in docs for t in d.tags],
        )

        s.run(
            """
            UNWIND $rows AS row
            MATCH (d:Doc {corpus: $corpus, path: row.doc})
            MERGE (src:Source {corpus: $corpus, path: row.source})
            MERGE (d)-[:CITES]->(src)
            """,
            corpus=corpus,
            rows=[{"doc": d.path, "source": s_} for d in docs for s_ in d.sources],
        )

        # MATCH on both ends, not MERGE: the loader has already dropped links
        # whose target does not exist, so a miss here means the two disagree.
        # Creating the node instead would paper over that with a titleless Doc
        # that a citation could then validate against.
        s.run(
            """
            UNWIND $rows AS row
            MATCH (a:Doc {corpus: $corpus, path: row.src})
            MATCH (b:Doc {corpus: $corpus, path: row.dst})
            MERGE (a)-[:LINKS_TO]->(b)
            """,
            corpus=corpus,
            rows=[{"src": d.path, "dst": link} for d in docs for link in d.links],
        )

        s.run(
            """
            UNWIND $rows AS row
            MATCH (d:Doc {corpus: $corpus, path: row.doc})
            MERGE (c:Chunk {corpus: $corpus, id: row.id})
            SET c.text = row.text,
                c.heading_path = row.heading_path,
                c.ord = row.ord,
                c.embedding = row.embedding
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            corpus=corpus,
            rows=[
                {
                    "doc": c.doc_path,
                    "id": c.id,
                    "text": c.text,
                    "heading_path": list(c.heading_path),
                    "ord": c.ord,
                    "embedding": vec,
                }
                for c, vec in zip(chunks, vectors, strict=True)
            ],
        )

    return BuildCounts(
        docs=len(docs),
        chunks=len(chunks),
        tags=len({t for d in docs for t in d.tags}),
        sources=len({s_ for d in docs for s_ in d.sources}),
        links=sum(len(d.links) for d in docs),
        cites=sum(len(d.sources) for d in docs),
    )
