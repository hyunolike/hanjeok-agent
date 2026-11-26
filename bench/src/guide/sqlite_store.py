"""Immutable public-data snapshots. Fixed SQL, exact cosine, bounded page cache.

The operator writes a new file; serving never refreshes or mutates this file.
The hosted query embedding is obtained before acquiring the connection lock.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import struct
import tempfile
from dataclasses import asdict
from pathlib import Path
from threading import Lock

import sqlite_vec

from bench.corpus.chunk import split
from guide.graph.read import EVENT_RADIUS_M, MAX_NAME_MATCHES, EventRow, PlaceRow, RelatedRow
from guide.sources import PAGE_CHARS, Page, group_gazetteer

SCHEMA = 1
DIM = 1024


def digest(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def vector_blob(value) -> bytes:
    try:
        values = struct.unpack(f"<{DIM}f", value) if isinstance(value, bytes) else value
        if (
            len(values) != DIM
            or any(not math.isfinite(v) for v in values)
            or abs(math.hypot(*values) - 1) > 1e-5
        ):
            raise ValueError("invalid_vector")
        return struct.pack(f"<{DIM}f", *values)
    except (TypeError, struct.error, OverflowError) as exc:
        raise ValueError("invalid_vector") from exc


def distance(lat, lng, other_lat, other_lng):
    if any(v is None for v in (lat, lng, other_lat, other_lng)):
        return None
    a, b = math.radians(lat), math.radians(other_lat)
    h = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * (
        math.sin(math.radians(other_lng - lng) / 2) ** 2
    )
    # Neo4j 5.26 CRSCalculator.GeographicCalculator.EARTH_RADIUS, in metres.
    return 6378140.0 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def write_snapshot(path, export, wiki, place_vectors, wiki_vectors, provenance) -> dict:
    """Atomic raw DB preparation from validated, already embedded source data."""
    path = Path(path)
    chunks = [c for doc in wiki.docs for c in split(doc.path, doc.body)]
    if (
        not export.places
        or not wiki.docs
        or wiki.dropped
        or set(place_vectors) != {p.id for p in export.places}
        or set(wiki_vectors) != {c.id for c in chunks}
        or len({d.path for d in wiki.docs}) != len(wiki.docs)
        or provenance.get("wiki_revision") != wiki.revision
        or not provenance.get("embedding_model")
        or provenance.get("embedding_model") != provenance.get("wiki_embedding_model")
    ):
        raise ValueError("snapshot_membership_or_identity")
    meta = {
        **provenance,
        "schema_version": SCHEMA,
        "exported_at": export.exported_at,
        "export_sha256": export.sha256,
        "source": export.source,
        "counts": export.counts,
        "wiki_docs": len(wiki.docs),
        "wiki_chunks": len(chunks),
    }
    meta["generation"] = hashlib.sha256(
        json.dumps(meta, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    os.close(fd)
    stage = Path(temporary)
    try:
        with sqlite3.connect(stage) as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                PRAGMA user_version=1;
                CREATE TABLE metadata (value TEXT NOT NULL);
                CREATE TABLE places (id INTEGER PRIMARY KEY, name_key TEXT NOT NULL,
                  region_code TEXT, covered INTEGER NOT NULL, record TEXT NOT NULL,
                  embedding BLOB NOT NULL CHECK(length(embedding)=4096));
                CREATE INDEX places_region ON places(region_code);
                CREATE TABLE related (base_id INTEGER REFERENCES places(id),
                  related_id INTEGER REFERENCES places(id), rank INTEGER, score REAL,
                  distance_km REAL, travel_minutes REAL, PRIMARY KEY(base_id, related_id));
                CREATE TABLE events (id TEXT PRIMARY KEY, place_id INTEGER REFERENCES places(id),
                  lat REAL, lng REAL, start_date TEXT, end_date TEXT, record TEXT NOT NULL);
                CREATE TABLE pages (path TEXT PRIMARY KEY, title TEXT NOT NULL);
                CREATE TABLE chunks (path TEXT REFERENCES pages(path), ord INTEGER,
                  text TEXT NOT NULL, embedding BLOB NOT NULL CHECK(length(embedding)=4096),
                  PRIMARY KEY(path, ord));
            """)
            db.execute("INSERT INTO metadata VALUES (?)", (json.dumps(meta),))
            for p in export.places:
                record = {k: v for k, v in asdict(p).items() if k in PlaceRow.__dataclass_fields__}
                db.execute(
                    "INSERT INTO places VALUES (?,?,?,?,?,?)",
                    (
                        p.id,
                        "".join(p.name.split()),
                        p.region_code,
                        int(p.has_congestion_data),
                        json.dumps(record, ensure_ascii=False),
                        vector_blob(place_vectors[p.id]),
                    ),
                )
            db.executemany(
                "INSERT INTO related VALUES (?,?,?,?,?,?)",
                (
                    (r.base_id, r.related_id, r.rank, r.score, r.distance_km, r.travel_minutes)
                    for r in export.related
                ),
            )
            for e in export.events:
                record = {k: v for k, v in asdict(e).items() if k in EventRow.__dataclass_fields__}
                db.execute(
                    "INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                    (
                        e.id,
                        e.place_id,
                        e.lat,
                        e.lng,
                        e.start_date,
                        e.end_date,
                        json.dumps(record, ensure_ascii=False),
                    ),
                )
            db.executemany("INSERT INTO pages VALUES (?,?)", ((d.path, d.title) for d in wiki.docs))
            db.executemany(
                "INSERT INTO chunks VALUES (?,?,?,?)",
                ((c.doc_path, c.ord, c.text, vector_blob(wiki_vectors[c.id])) for c in chunks),
            )
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("snapshot_references")
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("snapshot_integrity")
        manifest = {"database_sha256": digest(stage), "metadata": meta}
        os.replace(stage, path)
        return manifest
    finally:
        stage.unlink(missing_ok=True)


class SQLiteStore:
    def __init__(self, path, manifest_path, embedder):
        self._lock = Lock()
        self._embedder = embedder
        path = Path(path)
        manifest = json.loads(Path(manifest_path).read_text())
        if not isinstance(manifest, dict) or not isinstance(manifest.get("metadata"), dict):
            raise ValueError("snapshot_manifest_shape")
        if digest(path) != manifest.get("database_sha256"):
            raise ValueError("snapshot_hash")
        self._db = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, check_same_thread=False
        )
        try:
            self._db.enable_load_extension(True)
            try:
                sqlite_vec.load(self._db)
            finally:
                self._db.enable_load_extension(False)
            self._db.create_function("distance_m", 4, distance, deterministic=True)
            self._db.executescript(
                "PRAGMA cache_size=-8192; PRAGMA mmap_size=0; "
                "PRAGMA temp_store=FILE; PRAGMA query_only=ON;"
            )
            self.meta = json.loads(self._db.execute("SELECT value FROM metadata").fetchone()[0])
            if (
                self.meta != manifest.get("metadata")
                or self._db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA
                or self.meta.get("schema_version") != SCHEMA
                or not embedder.model_id
                or self.meta.get("embedding_model") != embedder.model_id
                or self.meta.get("wiki_embedding_model") != embedder.model_id
            ):
                raise ValueError("snapshot_identity_or_schema")
            counts = {
                table: self._db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("places", "related", "events", "pages", "chunks")
            }
            counts["regions"] = self._db.execute(
                "SELECT count(DISTINCT region_code) FROM places WHERE region_code != ''"
            ).fetchone()[0]
            expected = {
                **self.meta["counts"],
                "pages": self.meta["wiki_docs"],
                "chunks": self.meta["wiki_chunks"],
            }
            if counts != expected or not counts["places"] or not counts["chunks"]:
                raise ValueError("snapshot_count")
            self.places = SQLitePlaces(self)
            self.policy = SQLitePolicy(self)
        except Exception:
            self._db.close()
            raise

    def query(self, sql, parameters=()):
        with self._lock:
            return self._db.execute(sql, parameters).fetchall()

    def close(self):
        with self._lock:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _place(record):
    return PlaceRow(**json.loads(record))


class SQLitePlaces:
    def __init__(self, store):
        self._store = store
        self.exported_at = store.meta["exported_at"]
        self._gazetteer = group_gazetteer(
            (p.id, p.name, key, p.region_label, p.has_congestion_data)
            for key, record in store.query(
                "SELECT name_key, record FROM places ORDER BY covered DESC,id"
            )
            for p in [_place(record)]
        )

    def search(self, text, *, limit, region_code):
        blob = vector_blob(self._store._embedder.embed_query(text))
        return [
            _place(row[0])
            for row in self._store.query(
                "SELECT record FROM places WHERE (? IS NULL OR region_code=?) "
                "ORDER BY vec_distance_cosine(embedding,?),id LIMIT ?",
                (region_code, region_code, blob, limit),
            )
        ]

    def detail(self, place_id):
        rows = self._store.query("SELECT record FROM places WHERE id=?", (place_id,))
        return _place(rows[0][0]) if rows else None

    def match_name(self, name):
        key = "".join(name.split())
        if not key:
            return []
        return [
            _place(r[0])
            for r in self._store.query(
                "SELECT record FROM places WHERE instr(name_key,?)>0 ORDER BY "
                "CASE WHEN name_key=? THEN 0 WHEN substr(name_key,1,length(?))=? THEN 1 ELSE 2 END,"
                "covered DESC,length(name_key),id LIMIT ?",
                (key, key, key, key, MAX_NAME_MATCHES),
            )
        ]

    def related(self, place_id, *, limit):
        return [
            RelatedRow(_place(r[0]), *r[1:])
            for r in self._store.query(
                "SELECT p.record,r.rank,r.score,r.distance_km,r.travel_minutes FROM related r "
                "JOIN places p ON p.id=r.related_id WHERE r.base_id=? "
                "ORDER BY r.rank IS NULL,r.rank,r.score IS NULL DESC,r.score DESC,p.id LIMIT ?",
                (place_id, limit),
            )
        ]

    def events(self, place_id, *, on):
        p = self.detail(place_id)
        if p is None:
            return []
        return [
            EventRow(**json.loads(r[0]))
            for r in self._store.query(
                "SELECT record FROM events WHERE (place_id=? OR (place_id IS NULL AND "
                "distance_m(lat,lng,?,?)<=?)) AND (? IS NULL OR (start_date<=? AND ?<=end_date)) "
                "ORDER BY start_date,id",
                (place_id, p.lat, p.lng, EVENT_RADIUS_M, on, on, on),
            )
        ]

    def gazetteer(self):
        return self._gazetteer


class SQLitePolicy:
    def __init__(self, store):
        self._store = store

    def page(self, path):
        rows = self._store.query(
            "SELECT p.title,c.text FROM pages p JOIN chunks c "
            "ON c.path=p.path WHERE p.path=? ORDER BY c.ord",
            (path,),
        )
        return (
            Page(path, rows[0][0], "\n\n".join(r[1] for r in rows)[:PAGE_CHARS]) if rows else None
        )

    def search(self, text, *, limit):
        blob = vector_blob(self._store._embedder.embed_query(text))
        rows = self._store.query(
            "SELECT path FROM chunks ORDER BY vec_distance_cosine(embedding,?),path,ord LIMIT ?",
            (blob, limit * 3),
        )
        paths = list(dict.fromkeys(r[0] for r in rows))[:limit]
        return [self.page(path) for path in paths]
