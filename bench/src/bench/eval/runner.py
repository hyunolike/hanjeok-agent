"""Record every arm, including failures, and audit whether pairs are comparable."""

from __future__ import annotations

import fcntl
import json
import os
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bench.answer.pipeline import AnswerResult
from bench.runtime import BenchError


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    pair_id: str
    started_at: str
    question_id: str
    question: str
    corpus: str
    corpus_revision: str | None
    corpus_generation: str | None
    corpus_size: int | None
    strategy: str
    supplied: list[dict]
    answer: str | None
    cited_paths: list[str]
    outcome: str
    cause: str | None
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: int
    model: dict
    repair_count: int
    inputs: dict | None
    retrieval: dict
    model_calls: int
    provider_errors: list[dict] = dataclass_field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def input_diff(whole: RunRecord, graph: RunRecord) -> dict:
    left, right = whole.inputs, graph.inputs
    if left is None or right is None:
        return {"shared_equal": False, "differences": ["inputs unavailable"]}
    differences = [
        key
        for key in sorted(left.keys() | right.keys())
        if key != "user" and left.get(key) != right.get(key)
    ]
    try:
        luser, ruser = json.loads(left["user"]), json.loads(right["user"])
        differences += [
            key for key in sorted(luser.keys() | ruser.keys()) if luser.get(key) != ruser.get(key)
        ]
    except (KeyError, TypeError, ValueError):
        differences.append("unreadable user input")
    return {
        "shared_equal": all(key == "supplied" for key in differences),
        "differences": differences,
    }


@dataclass(frozen=True, slots=True)
class PairResult:
    pair_id: str
    whole: RunRecord
    graph: RunRecord
    valid: bool
    cause: str | None
    diff: dict

    @property
    def scoring_runs(self) -> tuple[RunRecord, ...]:
        if not self.valid or any(
            r.outcome not in ("answered", "no_grounds") for r in (self.whole, self.graph)
        ):
            return ()
        return (self.whole, self.graph)

    def to_dict(self, *, show_diff: bool = False) -> dict:
        body = {
            "pair_id": self.pair_id,
            "valid": self.valid,
            "cause": self.cause,
            "runs": [self.whole.to_dict(), self.graph.to_dict()],
        }
        if show_diff:
            body["input_diff"] = self.diff
        return body


def pair_records(whole: RunRecord, graph: RunRecord) -> PairResult:
    differences = []
    if (whole.strategy, graph.strategy) != ("whole", "graph"):
        differences.append("strategy")
    for field in (
        "pair_id",
        "question_id",
        "question",
        "corpus",
        "corpus_revision",
        "corpus_generation",
        "corpus_size",
        "model",
    ):
        if getattr(whole, field) != getattr(graph, field):
            differences.append(field)
    for field in ("corpus_revision", "corpus_generation", "corpus_size"):
        if getattr(whole, field) is None or getattr(graph, field) is None:
            differences.append(field + " unavailable")
    diff = input_diff(whole, graph)
    if not diff["shared_equal"]:
        differences.extend(key for key in diff["differences"] if key != "supplied")
    cause = "pair invalid: " + ", ".join(differences) if differences else None
    return PairResult(whole.pair_id, whole, graph, not differences, cause, diff)


def _check_boundary(stream) -> None:
    stream.seek(0, os.SEEK_END)
    if stream.tell():
        stream.seek(-1, os.SEEK_END)
        if stream.read(1) != b"\n":
            raise BenchError("load_failed", "artifact has an incomplete JSONL tail")


def _append(path: Path, record: dict) -> None:
    # Multiple local CLI processes may share a daily artifact. Lock the file
    # while writing one complete JSONL row; flush evidence before the next call.
    try:
        with path.open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            _check_boundary(stream)
            stream.write(
                (json.dumps(record, ensure_ascii=False, default=str) + "\n").encode("utf-8")
            )
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise BenchError("load_failed", "run artifact could not be written") from None


class PairRunner:
    def __init__(self, runtime, runs_file: Path):
        self.runtime = runtime
        self.runs_file = Path(runs_file)
        self.pairs_file = self.runs_file.with_suffix(".pairs.jsonl")

    def _prepare(self) -> None:
        try:
            self.runs_file.parent.mkdir(parents=True, exist_ok=True)
            for path in (self.runs_file, self.pairs_file):
                with path.open("a+b") as stream:
                    fcntl.flock(stream, fcntl.LOCK_EX)
                    _check_boundary(stream)
        except OSError:
            raise BenchError("load_failed", "run artifact destination unavailable") from None

    def run(
        self, *, pair_id: str, question_id: str, question: str, corpus: str, strategy: str
    ) -> RunRecord:
        started_at = datetime.now(UTC).isoformat()
        started = time.monotonic()
        model = deepcopy(self.runtime.model_settings)
        try:
            result = self.runtime.ask(question, corpus, strategy)
        except BenchError as error:
            result = error.result or AnswerResult(
                str(uuid4()),
                error.outcome,
                None,
                (),
                (),
                "",
                0,
                0,
                int((time.monotonic() - started) * 1000),
                0,
                error.cause,
            )
        except Exception:
            result = AnswerResult(
                str(uuid4()),
                "load_failed",
                None,
                (),
                (),
                "",
                0,
                0,
                int((time.monotonic() - started) * 1000),
                0,
                "local runtime unavailable",
            )
        successful = result.outcome == "answered"
        record = RunRecord(
            result.run_id,
            pair_id,
            started_at,
            question_id,
            question,
            corpus,
            result.corpus_revision or None,
            result.corpus_generation,
            result.corpus_size,
            strategy,
            result.to_dict(show_supplied=True)["supplied"],
            result.answer if successful else None,
            list(result.citations) if successful else [],
            result.outcome,
            result.cause,
            result.prompt_tokens,
            result.completion_tokens,
            result.elapsed_ms,
            model,
            result.repair_count,
            deepcopy(result.inputs),
            {"mode": "all-corpus-chunks"}
            if strategy == "whole"
            else {
                "mode": "corpus-filtered-exact-cosine",
                "k": 5,
                "min_score": 0.75,
                "expansion_limit": 8,
                "summary_chars": 240,
            },
            result.model_calls,
            list(result.provider_errors),
        )
        _append(self.runs_file, record.to_dict())
        return record

    def pair(self, *, question_id: str, question: str, corpus: str) -> PairResult:
        self._prepare()
        pair_id = str(uuid4())
        runs = [
            self.run(
                pair_id=pair_id,
                question_id=question_id,
                question=question,
                corpus=corpus,
                strategy=strategy,
            )
            for strategy in ("whole", "graph")
        ]
        result = pair_records(*runs)
        _append(
            self.pairs_file,
            {
                "pair_id": pair_id,
                "valid": result.valid,
                "cause": result.cause,
                "whole_run_id": result.whole.run_id,
                "graph_run_id": result.graph.run_id,
                "input_diff": result.diff,
            },
        )
        return result

    def run_set(self, question_set, *, corpus: str):
        """Yield every pair, continuing past recorded arm failures.

        Artifact failures still stop execution: another call must not be made
        when the preceding evidence could not be saved.
        """
        for question in question_set.questions:
            yield self.pair(question_id=question.id, question=question.question, corpus=corpus)
