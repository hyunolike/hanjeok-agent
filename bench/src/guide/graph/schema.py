"""Labels, constraints and indexes for the guide's part of the graph.

The wiki's labels (`Doc`, `Chunk`, …) belong to the bench and are untouched.
Places get their own label and their own vector index so a place search never
has to scan or filter wiki chunks.

Every node carries `corpus` and `generation`. `generation` is what lets a
refresh build a complete new copy beside the one being served; `corpus` is what
lets a test, or a second export, do that without touching another's copy.
"""

from __future__ import annotations

from neo4j import Driver

from bench.graph.store import EMBEDDING_DIM, session

PLACE_INDEX = "place_embedding"
LABELS = ("Place", "Region", "Event")

SCHEMA = [
    # A second write of the same place within one generation would double every
    # count the refresh verifies. The constraint makes that a failure, not a drift.
    "CREATE CONSTRAINT place_identity IF NOT EXISTS "
    "FOR (p:Place) REQUIRE (p.generation, p.id) IS UNIQUE",
    "CREATE CONSTRAINT region_identity IF NOT EXISTS "
    "FOR (r:Region) REQUIRE (r.generation, r.code) IS UNIQUE",
    "CREATE CONSTRAINT event_identity IF NOT EXISTS "
    "FOR (e:Event) REQUIRE (e.generation, e.id) IS UNIQUE",
    # The bench creates this one too; repeated here so the guide does not
    # depend on the bench having been run first.
    "CREATE CONSTRAINT corpus_identity IF NOT EXISTS FOR (c:Corpus) REQUIRE c.name IS UNIQUE",
    # Name resolution runs before the first model call, on every question.
    "CREATE INDEX place_name_key IF NOT EXISTS FOR (p:Place) ON (p.generation, p.name_key)",
    "CREATE INDEX place_generation IF NOT EXISTS FOR (p:Place) ON (p.generation)",
]


def ensure_schema(driver: Driver) -> None:
    with session(driver) as s:
        for statement in SCHEMA:
            s.run(statement).consume()
        s.run(
            f"""
            CREATE VECTOR INDEX {PLACE_INDEX} IF NOT EXISTS
            FOR (p:Place) ON (p.embedding)
            OPTIONS {{ indexConfig: {{
                `vector.dimensions`: $dim,
                `vector.similarity_function`: 'cosine'
            }} }}
            """,
            dim=EMBEDDING_DIM,
        ).consume()
        # A query issued while the index is still populating returns nothing
        # rather than failing, which reads as "no such place".
        s.run("CALL db.awaitIndexes(120)").consume()
