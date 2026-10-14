"""Every read the guide makes of its graph. Fixed queries, parameters only.

Nothing here is composed from model output: a lookup validates its inputs and
calls one of these functions with them (constitution, Principle VI). Every
function takes the generation to read, so one question sees one copy even if a
refresh activates another while it is being answered.

Related places are returned in Hanjeok's order — `rank` ascending, unranked
last, then `score` descending — and no caller re-sorts them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from neo4j import Driver
from neo4j_graphrag.retrievers import VectorCypherRetriever

from bench.graph.store import session
from guide.graph.schema import PLACE_INDEX
from guide.loader import CORPUS

# A festival has coordinates and no place. It is shown for a place when it is
# this close, which in a city is "at or beside it".
EVENT_RADIUS_M = 1000
MAX_NAME_MATCHES = 10

_PLACE = """
    p.id AS id, p.name AS name, p.region_code AS region_code, p.region_label AS region_label,
    p.category_mid AS category_mid, p.category_small AS category_small,
    p.summary AS summary, p.overview AS overview, p.address AS address,
    p.lat AS lat, p.lng AS lng, p.has_congestion_data AS has_congestion_data
"""


@dataclass(frozen=True, slots=True)
class Active:
    generation: str
    exported_at: str
    export_sha256: str
    counts: dict[str, int]
    source: str = ""


@dataclass(frozen=True, slots=True)
class PlaceRow:
    id: int
    name: str
    region_code: str | None
    region_label: str | None
    category_mid: str | None
    category_small: str | None
    summary: str | None
    overview: str | None
    address: str | None
    lat: float | None
    lng: float | None
    has_congestion_data: bool


@dataclass(frozen=True, slots=True)
class RelatedRow:
    place: PlaceRow
    rank: int | None
    score: float | None
    distance_km: float | None
    travel_minutes: float | None


@dataclass(frozen=True, slots=True)
class EventRow:
    id: str
    kind: str
    name: str
    start_date: str
    end_date: str
    place_text: str | None


def _place(row) -> PlaceRow:
    return PlaceRow(**{field: row[field] for field in PlaceRow.__dataclass_fields__})


def active(driver: Driver, corpus: str = CORPUS) -> Active | None:
    """The copy to read, or `None` when there is none — a 503, never an empty answer."""
    with session(driver) as s:
        row = s.run(
            "MATCH (c:Corpus {name: $corpus}) WHERE c.active_generation IS NOT NULL "
            "RETURN c.active_generation AS generation, c.exported_at AS exported_at, "
            "c.export_sha256 AS sha, c.counts_json AS counts, c.export_source AS source",
            corpus=corpus,
        ).single()
    if row is None:
        return None
    return Active(
        row["generation"],
        row["exported_at"],
        row["sha"],
        json.loads(row["counts"]),
        row["source"] or "",
    )


def match_name(driver: Driver, generation: str, name: str) -> list[PlaceRow]:
    """Places whose name is, starts with, or contains `name`, spaces ignored.

    In that order, at most ten. Used for browsing by name; a question's own
    place names are resolved against the whole gazetteer instead, where an
    exact name must win outright.
    """
    key = "".join(name.split())
    if not key:
        return []
    with session(driver) as s:
        rows = s.run(
            f"""
            MATCH (p:Place {{generation: $generation}})
            WHERE p.name_key CONTAINS $key
            WITH p, CASE WHEN p.name_key = $key THEN 0
                         WHEN p.name_key STARTS WITH $key THEN 1 ELSE 2 END AS tier
            RETURN tier, {_PLACE}
            ORDER BY tier, p.has_congestion_data DESC, size(p.name_key), p.id
            LIMIT $limit
            """,
            generation=generation,
            key=key,
            limit=MAX_NAME_MATCHES,
        ).data()
    return [_place(row) for row in rows]


def cypher_retriever(
    driver: Driver, index_name: str, retrieval_query: str
) -> VectorCypherRetriever:
    """A `VectorCypherRetriever` that can take `filters`.

    neo4j-graphrag 1.21.0 reads the index's embedding property into
    `_embedding_node_property` but `VectorCypherRetriever` looks for it under
    `_node_embedding_property`, which therefore stays `None`, and any filtered
    search stops with "Vector Search with filters requires: …". The plain
    `VectorRetriever` uses the first name and works. Reported upstream as
    neo4j/neo4j-graphrag-python#540 with a fix proposed in #541, both still
    open on 2026-10-14 and the mismatch still on `main`. Until that is merged
    the value is copied across here; `test_guide_graph.py` fails if a
    later version makes this unnecessary in a way that breaks it.
    """
    retriever = VectorCypherRetriever(
        driver, index_name=index_name, retrieval_query=retrieval_query
    )
    if getattr(retriever, "_node_embedding_property", None) is None:
        retriever._node_embedding_property = retriever._embedding_node_property
    return retriever


_SEARCH_RETURN = f"WITH node AS p, score RETURN score, {_PLACE} ORDER BY score DESC, p.id"


def search(
    driver: Driver,
    generation: str,
    vector: list[float],
    *,
    limit: int = 5,
    region_code: str | None = None,
) -> list[tuple[PlaceRow, float]]:
    """Nearest places by text similarity, through neo4j-graphrag's retriever.

    `VectorCypherRetriever` runs the similarity search and then a Cypher
    fragment over each hit. The fragment here is fixed text that only shapes
    the columns; the model has no part in it.

    Generation and region go in as the retriever's `filters`, which it applies
    **before** ranking. That matters during a refresh, when two generations of
    every place exist: filtering after ranking would let the other generation
    crowd the top results, and an earlier version of this function had to ask
    the index for twenty times what it needed to get round that.
    """
    filters = {"generation": generation}
    if region_code is not None:
        filters["region_code"] = region_code
    retriever = cypher_retriever(driver, PLACE_INDEX, _SEARCH_RETURN)
    raw = retriever.get_search_results(query_vector=list(vector), top_k=limit, filters=filters)
    return [(_place(record), record["score"]) for record in raw.records]


def detail(driver: Driver, generation: str, place_id: int) -> PlaceRow | None:
    with session(driver) as s:
        row = s.run(
            f"MATCH (p:Place {{generation: $generation, id: $id}}) RETURN {_PLACE}",
            generation=generation,
            id=place_id,
        ).single()
    return _place(row) if row else None


def related(driver: Driver, generation: str, place_id: int, *, limit: int = 10) -> list[RelatedRow]:
    with session(driver) as s:
        rows = s.run(
            f"""
            MATCH (:Place {{generation: $generation, id: $id}})-[r:RELATED_TO]->(p:Place)
            RETURN r.rank AS rank, r.score AS score, r.distance_km AS distance_km,
                   r.travel_minutes AS travel_minutes, {_PLACE}
            ORDER BY r.rank IS NULL, r.rank, r.score DESC, p.id
            LIMIT $limit
            """,
            generation=generation,
            id=place_id,
            limit=limit,
        ).data()
    return [
        RelatedRow(
            _place(row), row["rank"], row["score"], row["distance_km"], row["travel_minutes"]
        )
        for row in rows
    ]


def events(
    driver: Driver, generation: str, place_id: int, *, on: str | None = None
) -> list[EventRow]:
    """Events tied to a place or held beside it, optionally only those running
    on one day. Dates are ISO strings, so comparing them as text is comparing
    them as dates."""
    with session(driver) as s:
        rows = s.run(
            """
            MATCH (p:Place {generation: $generation, id: $id})
            MATCH (e:Event {generation: $generation})
            WHERE (EXISTS { (e)-[:HELD_AT]->(p) }
                   OR (NOT EXISTS { (e)-[:HELD_AT]->(:Place) }
                       AND e.lat IS NOT NULL AND p.lat IS NOT NULL
                       AND point.distance(point({latitude: e.lat, longitude: e.lng}),
                                          point({latitude: p.lat, longitude: p.lng})) <= $radius))
              AND ($on IS NULL OR (e.start_date <= $on AND $on <= e.end_date))
            RETURN e.id AS id, e.kind AS kind, e.name AS name, e.start_date AS start_date,
                   e.end_date AS end_date, e.place_text AS place_text
            ORDER BY e.start_date, e.id
            """,
            generation=generation,
            id=place_id,
            on=on,
            radius=EVENT_RADIUS_M,
        ).data()
    return [EventRow(**row) for row in rows]


def gazetteer(driver: Driver, generation: str) -> list[tuple[int, str, str, str | None, bool]]:
    """Every place's id, name, name key and region. Names are matched against a
    question before any model is called, so this is read once per generation
    and held in memory by the caller."""
    with session(driver) as s:
        rows = s.run(
            "MATCH (p:Place {generation: $generation}) "
            "RETURN p.id AS id, p.name AS name, p.name_key AS key, p.region_label AS region, "
            "p.has_congestion_data AS covered "
            "ORDER BY p.has_congestion_data DESC, p.id",
            generation=generation,
        ).values()
    return [tuple(row) for row in rows]
