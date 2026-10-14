"""What a lookup reads from: places, and policy documents.

Two small interfaces so the lookups and the agent can be tested with no
database. The graph-backed implementations are thin: each method is one fixed
read from `guide.graph.read` or the bench's wiki corpus.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from neo4j import Driver

from bench.graph.store import VECTOR_INDEX as WIKI_INDEX
from bench.graph.store import session
from guide.graph import read
from guide.graph.read import EventRow, PlaceRow, RelatedRow
from guide.scope import Candidate

WIKI_CORPUS = "wiki"
_CHUNK_TO_PAGE = (
    "WITH node, score MATCH (d:Doc {corpus: node.corpus})-[:HAS_CHUNK]->(node) "
    "RETURN d.path AS path, score ORDER BY score DESC, path"
)
PAGE_CHARS = 1800


@dataclass(frozen=True, slots=True)
class Page:
    path: str
    title: str
    text: str


class Places(Protocol):
    exported_at: str

    def search(self, text: str, *, limit: int, region_code: str | None) -> Sequence[PlaceRow]: ...
    def detail(self, place_id: int) -> PlaceRow | None: ...
    def match_name(self, name: str) -> Sequence[PlaceRow]: ...
    def related(self, place_id: int, *, limit: int) -> Sequence[RelatedRow]: ...
    def events(self, place_id: int, *, on: str | None) -> Sequence[EventRow]: ...
    def gazetteer(self) -> dict[str, Sequence[Candidate]]: ...


class Policy(Protocol):
    def page(self, path: str) -> Page | None: ...
    def search(self, text: str, *, limit: int) -> Sequence[Page]: ...


def group_gazetteer(rows) -> dict[str, list[Candidate]]:
    grouped: dict[str, list[Candidate]] = {}
    for place_id, name, key, region, covered in rows:
        grouped.setdefault(key, []).append(Candidate(place_id, name, region or "", bool(covered)))
    return grouped


class GraphPlaces:
    """One generation of the guide's graph. Built per question, so a question
    reads one copy from start to finish."""

    def __init__(self, driver: Driver, active: read.Active, embedder, gazetteer=None) -> None:
        self._driver, self._generation, self._embedder = driver, active.generation, embedder
        self.exported_at = active.exported_at
        self._gazetteer = gazetteer

    def search(self, text, *, limit, region_code):
        vector = self._embedder.embed_query(text)
        hits = read.search(
            self._driver, self._generation, vector, limit=limit, region_code=region_code
        )
        return [place for place, _ in hits]

    def detail(self, place_id):
        return read.detail(self._driver, self._generation, place_id)

    def match_name(self, name):
        return read.match_name(self._driver, self._generation, name)

    def related(self, place_id, *, limit):
        return read.related(self._driver, self._generation, place_id, limit=limit)

    def events(self, place_id, *, on):
        return read.events(self._driver, self._generation, place_id, on=on)

    def gazetteer(self):
        if self._gazetteer is None:
            self._gazetteer = group_gazetteer(read.gazetteer(self._driver, self._generation))
        return self._gazetteer


class GraphPolicy:
    """The wiki, as the bench loaded it. Read-only here."""

    def __init__(self, driver: Driver, embedder, corpus: str = WIKI_CORPUS) -> None:
        self._driver, self._embedder, self._corpus = driver, embedder, corpus

    def page(self, path):
        with session(self._driver) as s:
            row = s.run(
                "MATCH (d:Doc {corpus: $corpus, path: $path})-[:HAS_CHUNK]->(c:Chunk) "
                "WITH d, c ORDER BY c.ord RETURN d.title AS title, collect(c.text) AS texts",
                corpus=self._corpus,
                path=path,
            ).single()
        if row is None:
            return None
        return Page(path, row["title"], "\n\n".join(row["texts"])[:PAGE_CHARS])

    def search(self, text, *, limit):
        # The wiki's chunks, nearest first, through the same retriever the
        # places use. The fragment maps each chunk to its page; a page is
        # returned once, at the rank of its best chunk.
        retriever = read.cypher_retriever(self._driver, WIKI_INDEX, _CHUNK_TO_PAGE)
        raw = retriever.get_search_results(
            query_vector=self._embedder.embed_query(text),
            top_k=limit * 3,
            filters={"corpus": self._corpus},
        )
        paths = list(dict.fromkeys(record["path"] for record in raw.records))[:limit]
        return [page for page in (self.page(path) for path in paths) if page is not None]
