"""Corpus-scoped similarity search and bounded, one-hop graph expansion.

Neo4j 5's shared ANN index cannot pre-filter by corpus. Filtering its top-k
afterwards can hide every relevant passage behind another corpus's hits. Use
exact cosine ranking inside the selected corpus, with stable tie-breaking.
This retrieval mode must be recorded when interpreting benchmark latency.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from neo4j import Driver

from bench.graph.store import EMBEDDING_DIM, session


@dataclass(frozen=True, slots=True)
class Passage:
    doc: str
    chunk: str
    text: str
    title: str
    attrs: Mapping[str, Any] = field(default_factory=dict)
    heading_path: tuple[str, ...] = ()
    score: float | None = None
    expanded: bool = False


def _passage(row: Mapping[str, Any], *, expanded: bool = False) -> Passage:
    text = row["text"]
    if expanded:
        text = re.split(r"(?<=[.!?。])\s+|\n", text.strip(), maxsplit=1)[0][:240]
    return Passage(
        doc=row["doc"],
        chunk=row["chunk"],
        text=text,
        title=row["title"],
        attrs=json.loads(row["attrs"] or "{}"),
        heading_path=tuple(row["heading_path"] or ()),
        score=row.get("score"),
        expanded=expanded,
    )


def vector_search(
    driver: Driver,
    corpus: str,
    vector: Sequence[float],
    *,
    k: int = 5,
    min_score: float = 0.75,
) -> list[Passage]:
    if len(vector) != EMBEDDING_DIM or not all(math.isfinite(v) for v in vector):
        raise ValueError("query embedding has invalid dimensions or values")
    if not any(vector):
        raise ValueError("query embedding has no direction")
    if k < 1 or not 0 <= min_score <= 1:
        raise ValueError("invalid retrieval bounds")
    with session(driver) as s:
        rows = s.run(
            "MATCH (d:Doc {corpus: $corpus})-[:HAS_CHUNK]->(c:Chunk {corpus: $corpus}) "
            "WHERE c.embedding IS NOT NULL "
            "WITH d, c, vector.similarity.cosine(c.embedding, $vector) AS score "
            "WHERE score >= $threshold "
            "RETURN d.path AS doc, c.id AS chunk, c.text AS text, d.title AS title, "
            "d.attrs_json AS attrs, c.heading_path AS heading_path, score "
            "ORDER BY score DESC, doc, chunk LIMIT $k",
            corpus=corpus,
            vector=list(vector),
            threshold=min_score,
            k=k,
        )
        return [_passage(dict(row)) for row in rows]


def expand(
    driver: Driver,
    corpus: str,
    seeds: Sequence[Passage],
    *,
    limit: int = 8,
) -> list[Passage]:
    if not seeds or limit <= 0:
        return []
    paths = sorted({p.doc for p in seeds})
    with session(driver) as s:
        rows = s.run(
            """
            MATCH (seed:Doc {corpus: $corpus}) WHERE seed.path IN $paths
            CALL (seed) {
                MATCH (seed)-[:LINKS_TO]-(d:Doc) RETURN d
                UNION
                MATCH (seed)-[:CITES]->(:Source)<-[:CITES]-(d:Doc) RETURN d
                UNION
                MATCH (seed)-[:TAGGED]->(:Tag)<-[:TAGGED]-(d:Doc) RETURN d
            }
            WITH DISTINCT d
            WHERE d.corpus = $corpus AND NOT d.path IN $paths
            WITH d ORDER BY d.path LIMIT $limit
            MATCH (d)-[:HAS_CHUNK]->(c:Chunk {corpus: $corpus})
            WITH d, c ORDER BY c.ord, c.id
            WITH d, head(collect(c)) AS c
            RETURN d.path AS doc, c.id AS chunk, c.text AS text, d.title AS title,
                   d.attrs_json AS attrs, c.heading_path AS heading_path
            ORDER BY doc
            """,
            corpus=corpus,
            paths=paths,
            limit=limit,
        )
        return [_passage(dict(row), expanded=True) for row in rows]


def document_paths(driver: Driver, corpus: str) -> set[str]:
    with session(driver) as s:
        return {
            row["path"]
            for row in s.run(
                "MATCH (d:Doc {corpus: $corpus}) RETURN d.path AS path",
                corpus=corpus,
            )
        }
