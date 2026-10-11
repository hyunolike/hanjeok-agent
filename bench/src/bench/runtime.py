"""One runtime shared by HTTP and CLI. Corpus files are always read-only."""

from __future__ import annotations

import os
from dataclasses import asdict, replace
from pathlib import Path, PurePosixPath
from threading import RLock

from neo4j.exceptions import DriverError, Neo4jError

from bench.answer.pipeline import AnswerPipeline, AnswerResult
from bench.answer.strategies import GraphStrategy, WholeStrategy
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
    def __init__(
        self, outcome: str, cause: str, status: int = 503, *, result: AnswerResult | None = None
    ):
        super().__init__(cause)
        self.outcome, self.cause, self.status = outcome, cause, status
        self.result = result


class BenchRuntime:
    def __init__(self, driver, embedder, model, loaders=None, *, max_input_bytes: int = 100_000):
        self.driver, self.embedder, self.model = driver, embedder, model
        self.loaders = loaders or {}
        self.max_input_bytes = max_input_bytes
        # A rebuild must not interleave with a question seeing its old revision.
        self._lock = RLock()

    @property
    def model_settings(self) -> dict:
        return dict(getattr(self.model, "settings", {"name": type(self.model).__name__}))

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
        if strategy not in ("graph", "whole"):
            raise BenchError("load_failed", "unknown strategy", 409)
        with self._lock:
            result = None
            try:
                snapshot = corpus_snapshot(self.driver, corpus)
                if snapshot is None:
                    raise BenchError("load_failed", "corpus is not loaded", 409)
                revision = snapshot[0]
                known = document_paths(self.driver, corpus)
                select = (
                    WholeStrategy(self.driver)
                    if strategy == "whole"
                    else GraphStrategy(self.driver, self.embedder)
                )
                pipeline = AnswerPipeline(select, self.model, max_input_bytes=self.max_input_bytes)
                result = pipeline.ask(question, corpus, revision, known)
                result = replace(result, corpus_size=len(known), corpus_generation=snapshot[1])
                if corpus_snapshot(self.driver, corpus) != snapshot:
                    cause = "corpus changed during the request"
                    raise BenchError(
                        "load_failed",
                        cause,
                        409,
                        result=replace(
                            result, outcome="load_failed", cause=cause, answer=None, citations=()
                        ),
                    )
                return result
            except BenchError:
                raise
            except Exception:
                cause = "graph or retrieval unavailable"
                failed = (
                    replace(result, outcome="load_failed", cause=cause, answer=None, citations=())
                    if result is not None
                    else None
                )
                raise BenchError("load_failed", cause, result=failed) from None

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
    max_input_bytes = int(os.environ.get("BENCH_MAX_INPUT_BYTES", "100000"))
    if max_input_bytes < 1:
        raise ValueError("invalid input budget")
    return BenchRuntime(
        driver_from_env(),
        LocalEmbedder(),
        LazyAnswerModel(),
        loaders,
        max_input_bytes=max_input_bytes,
    )
