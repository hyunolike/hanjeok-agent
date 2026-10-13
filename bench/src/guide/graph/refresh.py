"""Replace the guide's copy of Hanjeok's data without ever being without one.

A refresh writes a complete new generation beside the active one, checks that
what it wrote is what the export said it would be, and only then moves the
pointer on the `Corpus` node. Readers follow the pointer, so they see the old
copy until the instant the new one is whole.

The bench's `rebuild` drops first and builds second, which is fine for a
measurement run from a terminal and wrong for something answering questions: a
failure in the middle leaves nothing (spec FR-020).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from array import array
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from neo4j import Driver

from bench.graph.store import EMBEDDING_DIM, session
from guide.export import Export
from guide.graph.schema import LABELS, ensure_schema
from guide.loader import CORPUS, place_text

BATCH = 500


class RefreshError(Exception):
    """The refresh did not activate. The previous copy is still the active one."""

    def __init__(self, cause: str, detail: str) -> None:
        super().__init__(f"{cause}: {detail}")
        self.cause = cause
        self.detail = detail


@dataclass(frozen=True, slots=True)
class RefreshResult:
    corpus: str
    generation: str
    counts: dict[str, int]
    exported_at: str
    export_sha256: str
    embedded: int
    """Places whose text was sent to the embedder this time."""

    reused: int
    """Places whose embedding came from the cache."""


class EmbeddingCache:
    """Embeddings on disk, keyed by what was embedded and by which model.

    Embedding ten thousand places takes minutes on a CPU. Most of an export is
    unchanged from the last one, so a refresh should pay only for what changed.
    The model's identity is part of the key: a cache that survives a model swap
    would mix two spaces in one index, and nothing would look wrong.
    """

    def __init__(self, path: Path | str | None, model_id: str) -> None:
        self._model_id = model_id
        self._db: sqlite3.Connection | None = None
        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS embedding (key TEXT PRIMARY KEY, vector BLOB)"
            )

    def key(self, text: str) -> str:
        return hashlib.sha256(f"{self._model_id}\0{text}".encode()).hexdigest()

    def get(self, text: str) -> list[float] | None:
        if self._db is None:
            return None
        row = self._db.execute(
            "SELECT vector FROM embedding WHERE key = ?", (self.key(text),)
        ).fetchone()
        if row is None:
            return None
        vector = array("f")
        vector.frombytes(row[0])
        return list(vector)

    def put(self, text: str, vector: Sequence[float]) -> None:
        if self._db is None:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO embedding VALUES (?, ?)",
            (self.key(text), array("f", vector).tobytes()),
        )

    def close(self) -> None:
        if self._db is not None:
            self._db.commit()
            self._db.close()
            self._db = None


def _batches(rows: list, size: int = BATCH):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _embed(
    export: Export, embedder, cache: EmbeddingCache
) -> tuple[dict[int, list[float]], int, int]:
    texts = {place.id: place_text(place) for place in export.places}
    vectors: dict[int, list[float]] = {}
    missing: list[int] = []
    for place_id, text in texts.items():
        cached = cache.get(text)
        if cached is None:
            missing.append(place_id)
        else:
            vectors[place_id] = cached
    reused = len(vectors)
    # Batched so a crash partway through keeps what was already embedded.
    for batch in _batches(missing, 64):
        embedded = embedder.embed([texts[place_id] for place_id in batch])
        if len(embedded) != len(batch):
            raise RefreshError(
                "embedding_failed", f"asked for {len(batch)} vectors, got {len(embedded)}"
            )
        for place_id, vector in zip(batch, embedded, strict=True):
            if len(vector) != EMBEDDING_DIM:
                raise RefreshError(
                    "embedding_failed",
                    f"vector of {len(vector)} dimensions, index has {EMBEDDING_DIM}",
                )
            vectors[place_id] = list(vector)
            cache.put(texts[place_id], vector)
    return vectors, len(missing), reused


def _write(
    driver: Driver, corpus: str, generation: str, export: Export, vectors: dict[int, list[float]]
) -> None:
    scope = {"corpus": corpus, "generation": generation}
    places = [
        {
            **asdict(place),
            # Spaces removed, so "솔내한옥마을" finds "솔내 한옥마을".
            "name_key": "".join(place.name.split()),
            "embedding": vectors[place.id],
        }
        for place in export.places
    ]
    regions = [{"code": code, "label": label} for code, label in export.regions.items()]
    related = [asdict(link) for link in export.related]
    events = [asdict(event) for event in export.events]

    with session(driver) as s:
        for batch in _batches(places):
            s.run(
                """
                UNWIND $rows AS row
                CREATE (p:Place {corpus: $corpus, generation: $generation, id: row.id})
                SET p.name = row.name, p.name_key = row.name_key,
                    p.region_code = row.region_code, p.region_label = row.region_label,
                    p.content_type = row.content_type,
                    p.category_mid = row.category_mid, p.category_small = row.category_small,
                    p.summary = row.summary, p.overview = row.overview, p.address = row.address,
                    p.lat = row.lat, p.lng = row.lng,
                    p.has_congestion_data = row.has_congestion_data,
                    p.embedding = row.embedding
                """,
                rows=batch,
                **scope,
            ).consume()
        s.run(
            "UNWIND $rows AS row CREATE (:Region {corpus: $corpus, generation: $generation, "
            "code: row.code, label: row.label})",
            rows=regions,
            **scope,
        ).consume()
        s.run(
            """
            MATCH (p:Place {generation: $generation}) WHERE p.region_code IS NOT NULL
            MATCH (r:Region {generation: $generation, code: p.region_code})
            CREATE (p)-[:IN_REGION {generation: $generation}]->(r)
            """,
            **scope,
        ).consume()
        for batch in _batches(related):
            s.run(
                """
                UNWIND $rows AS row
                MATCH (a:Place {generation: $generation, id: row.base_id})
                MATCH (b:Place {generation: $generation, id: row.related_id})
                CREATE (a)-[:RELATED_TO {generation: $generation, rank: row.rank, score: row.score,
                                         distance_km: row.distance_km,
                                         travel_minutes: row.travel_minutes}]->(b)
                """,
                rows=batch,
                **scope,
            ).consume()
        for batch in _batches(events):
            s.run(
                """
                UNWIND $rows AS row
                CREATE (e:Event {corpus: $corpus, generation: $generation, id: row.id})
                SET e.kind = row.kind, e.name = row.name,
                    e.start_date = row.start_date, e.end_date = row.end_date,
                    e.lat = row.lat, e.lng = row.lng, e.place_text = row.place_text
                WITH e, row WHERE row.place_id IS NOT NULL
                MATCH (p:Place {generation: $generation, id: row.place_id})
                CREATE (e)-[:HELD_AT {generation: $generation}]->(p)
                """,
                rows=batch,
                **scope,
            ).consume()


def written_counts(driver: Driver, generation: str) -> dict[str, int]:
    with session(driver) as s:
        row = s.run(
            """
            CALL () { MATCH (p:Place {generation: $g}) RETURN count(p) AS places }
            CALL () { MATCH (:Place {generation: $g})-[r:RELATED_TO]->(:Place {generation: $g})
                   RETURN count(r) AS related }
            CALL () { MATCH (e:Event {generation: $g}) RETURN count(e) AS events }
            CALL () { MATCH (r:Region {generation: $g}) RETURN count(r) AS regions }
            RETURN places, related, events, regions
            """,
            g=generation,
        ).single()
        return dict(row)


def delete_generation(
    driver: Driver, corpus: str, *, generation: str | None = None, keep: str | None = None
) -> None:
    """Delete one generation of a corpus, or every generation except `keep`."""
    condition = "n.generation = $generation" if generation is not None else "n.generation <> $keep"
    with session(driver) as s:
        for label in LABELS:
            while True:
                row = s.run(
                    f"MATCH (n:{label} {{corpus: $corpus}}) WHERE {condition} "
                    "WITH n LIMIT 2000 DETACH DELETE n RETURN count(n) AS n",
                    corpus=corpus,
                    generation=generation,
                    keep=keep,
                ).single()
                if not row or row["n"] == 0:
                    break


def refresh(
    driver: Driver,
    export: Export,
    embedder,
    *,
    corpus: str = CORPUS,
    model_id: str = "unnamed",
    cache_path: Path | str | None = None,
    before_activate: Callable[[str], None] | None = None,
) -> RefreshResult:
    """Build a generation from `export` and make it the active one.

    `before_activate` runs after the new generation is written and verified,
    just before the pointer moves. Tests use it to fail at the one moment that
    matters; nothing else should need it.
    """
    ensure_schema(driver)
    generation = str(uuid4())
    cache = EmbeddingCache(cache_path, model_id)
    try:
        vectors, embedded, reused = _embed(export, embedder, cache)
        _write(driver, corpus, generation, export, vectors)

        counts = written_counts(driver, generation)
        if counts != export.counts:
            raise RefreshError("count_mismatch", f"export has {export.counts}, graph has {counts}")
        if before_activate is not None:
            before_activate(generation)

        with session(driver) as s:
            # One statement, so there is no instant at which the pointer names
            # a generation whose stamp belongs to another.
            s.run(
                """
                MERGE (c:Corpus {name: $corpus})
                SET c.active_generation = $generation, c.generation = $generation,
                    c.exported_at = $exported_at, c.export_sha256 = $sha, c.revision = $sha,
                    c.export_source = $source,
                    c.counts_json = $counts, c.docs = $docs, c.chunks = 0,
                    c.loaded_at = $loaded_at
                """,
                corpus=corpus,
                generation=generation,
                exported_at=export.exported_at,
                source=export.source,
                sha=export.sha256,
                counts=json.dumps(counts),
                docs=counts["places"] + counts["events"],
                loaded_at=datetime.now(UTC).isoformat(),
            ).consume()
    except BaseException as error:
        # Whatever was written is not the active copy and never will be.
        delete_generation(driver, corpus, generation=generation)
        if isinstance(error, RefreshError) or not isinstance(error, Exception):
            raise
        raise RefreshError("refresh_failed", f"{type(error).__name__}: {error}") from error
    finally:
        cache.close()

    # After the pointer has moved. If this is interrupted, the leftovers are
    # unreachable by any read and the next refresh removes them.
    delete_generation(driver, corpus, keep=generation)
    return RefreshResult(
        corpus, generation, counts, export.exported_at, export.sha256, embedded, reused
    )
