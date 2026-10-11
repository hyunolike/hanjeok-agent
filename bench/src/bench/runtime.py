"""One runtime shared by HTTP and CLI. Corpus files are always read-only."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from threading import RLock

from neo4j.exceptions import DriverError, Neo4jError

from bench.answer.pipeline import AnswerPipeline, AnswerResult
from bench.answer.strategies import GraphStrategy
from bench.corpus.loader import check_unique_paths
from bench.corpus.wiki import WikiLoader
from bench.graph.build import build
from bench.graph.query import document_paths
from bench.graph.store import (
    corpora,
    corpus_snapshot,
    driver_from_env,
    drop_corpus,
    ensure_schema,
    record_corpus,
)


class BenchError(Exception):
    def __init__(self, outcome: str, cause: str, status: int = 503):
        super().__init__(cause)
        self.outcome, self.cause, self.status = outcome, cause, status


class BenchRuntime:
    def __init__(self, driver, embedder, model, loaders=None):
        self.driver, self.embedder, self.model = driver, embedder, model
        self.loaders = loaders or {}
        # A rebuild must not interleave with a question seeing its old revision.
        self._lock = RLock()

    def list_corpora(self) -> list[dict]:
        with self._lock:
            try:
                return [asdict(c) for c in corpora(self.driver)]
            except (DriverError, Neo4jError):
                raise BenchError("load_failed", "graph unavailable") from None

    def rebuild(self, name: str) -> dict:
        loader = self.loaders.get(name)
        if loader is None:
            raise BenchError("load_failed", "corpus loader is not configured", 409)
        with self._lock:
            try:
                loaded = loader.load()
                check_unique_paths(loaded.docs)
                if not loaded.docs or any(d.corpus != name for d in loaded.docs):
                    raise ValueError("loader returned an empty or mixed corpus")
                # Read and validate first: a typo in the path must not erase a
                # previously loaded corpus. After dropping, the record stays
                # absent until the complete new graph has been built.
                ensure_schema(self.driver)
                drop_corpus(self.driver, name)
                counts = build(self.driver, loaded.docs, self.embedder)
                record_corpus(self.driver, name, loaded.revision, counts.docs, counts.chunks)
                return {
                    "name": name,
                    "revision": loaded.revision,
                    **asdict(counts),
                    "dropped": [
                        {
                            "source_path": _safe_ref(ref.source_path),
                            "target": _safe_ref(ref.target),
                            "kind": ref.kind,
                        }
                        for ref in loaded.dropped
                    ],
                }
            except Exception:
                raise BenchError(
                    "load_failed", "corpus rebuild failed; check local configuration"
                ) from None

    def ask(self, question: str, corpus: str, strategy: str) -> AnswerResult:
        if strategy != "graph":
            # Phase 4 implements whole; quietly running graph here invalidates
            # the comparison before there is even a runner to detect it.
            raise BenchError("load_failed", "whole strategy is not implemented yet", 409)
        with self._lock:
            try:
                snapshot = corpus_snapshot(self.driver, corpus)
                if snapshot is None:
                    raise BenchError("load_failed", "corpus is not loaded", 409)
                revision = snapshot[0]
                known = document_paths(self.driver, corpus)
                pipeline = AnswerPipeline(GraphStrategy(self.driver, self.embedder), self.model)
                result = pipeline.ask(question, corpus, revision, known)
                if corpus_snapshot(self.driver, corpus) != snapshot:
                    raise BenchError("load_failed", "corpus changed during the request", 409)
                return result
            except BenchError:
                raise
            except Exception:
                raise BenchError("load_failed", "graph or retrieval unavailable") from None

    def close(self) -> None:
        self.driver.close()


def _safe_ref(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or (len(value) > 1 and value[1] == ":"):
        return "[outside corpus]"
    return value


def runtime_from_env() -> BenchRuntime:
    from bench.embeddings import LocalEmbedder
    from bench.models import LazyAnswerModel

    loaders = {}
    if root := os.environ.get("BENCH_WIKI_ROOT"):
        loaders["wiki"] = WikiLoader(Path(root))
    return BenchRuntime(driver_from_env(), LocalEmbedder(), LazyAnswerModel(), loaders)
