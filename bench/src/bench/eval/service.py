"""Frozen full-corpus evaluations and durable local background report jobs."""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from bench.eval.questions import QuestionSetLoader
from bench.eval.runner import PairRunner, _append
from bench.eval.score import build_report, score_pairs
from bench.runtime import BenchError

DEFAULT_ROOT = Path(__file__).resolve().parents[3]


class ReportStore:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, report_id):
        try:
            if str(UUID(report_id)) != report_id:
                raise ValueError("invalid id")
        except (ValueError, TypeError, AttributeError):
            raise BenchError("load_failed", "report not found", 404) from None
        return self.root / f"{report_id}.json"

    def put(self, report):
        path = self.path(report["report_id"])
        scratch = path.with_suffix(f".{uuid4()}.tmp")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with scratch.open("x") as stream:
                json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(scratch, path)
        except OSError:
            raise BenchError("load_failed", "report artifact destination unavailable") from None
        finally:
            scratch.unlink(missing_ok=True)

    def get(self, report_id):
        path = self.path(report_id)
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            raise BenchError("load_failed", "report not found", 404) from None


class EvaluationService:
    def __init__(
        self, runtime, questions=None, runs_root=None, reports_root=None, *, judge_factory=None
    ):
        self.runtime = runtime
        self.questions = questions or QuestionSetLoader(DEFAULT_ROOT / "questions")
        self.runs_root = Path(runs_root or DEFAULT_ROOT / "runs")
        self.store = ReportStore(reports_root or DEFAULT_ROOT / "reports")
        self.judge_factory = judge_factory or self._judge
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bench-eval")
        self._jobs = {}
        self._lock = RLock()

    def _judge(self):
        from bench.eval.judge import RagasJudge

        return RagasJudge(self.runtime.embedder)

    def _prepare(self, name, corpus, sizes, *, questions=None):
        questions = questions or self.questions.load(name)
        profile = self.runtime.corpus_context(corpus)
        questions.validate_corpus(corpus, profile["known_paths"])
        if sizes is not None and sizes != [profile["corpus_size"]]:
            raise BenchError(
                "load_failed",
                "corpus has no sampling loader; only its full loaded size is supported",
                409,
            )
        answer_model = self.runtime.model_settings
        report_id = str(uuid4())
        self.runs_root.mkdir(parents=True, exist_ok=True)
        runner = PairRunner(self.runtime, self.runs_root / f"{report_id}.jsonl")
        runner._prepare()
        # Verify report writes before paying for answer calls. Persisted running
        # markers become interrupted on another process; they are never immortal jobs.
        progress = {
            "report_id": report_id,
            "status": "running",
            "phase": "answering",
            "completed": 0,
            "total": 2 * len(questions.questions),
            "scores_completed": 0,
            "scores_total": 8 * len(questions.questions),
        }
        self.store.put(progress)
        with self._lock:
            self._jobs[report_id] = progress
        return report_id, questions, profile, answer_model, runner

    def _progress(self, report_id, **updates):
        with self._lock:
            self._jobs[report_id] = {**self._jobs[report_id], **updates}
            self.store.put(self._jobs[report_id])

    def _execute(self, report_id, questions, profile, answer_model, runner):
        try:
            pairs = []
            eligible = []
            for pair in runner.run_set(questions, corpus=profile["corpus"]):
                pairs.append(pair)
                eligible.append(
                    bool(pair.scoring_runs)
                    and all(
                        all(
                            getattr(run, k) == profile[k]
                            for k in ("corpus_revision", "corpus_generation", "corpus_size")
                        )
                        and run.model == answer_model
                        for run in (pair.whole, pair.graph)
                    )
                )
                self._progress(report_id, completed=2 * len(pairs))
            self._progress(report_id, phase="scoring")
            judge = self.judge_factory()
            scores_path = self.runs_root / f"{report_id}.scores.jsonl"
            scored = 0

            def on_score(row):
                nonlocal scored
                _append(scores_path, row)
                scored += 1
                self._progress(report_id, scores_completed=scored)

            # Execute with frozen question order; judge failures stay observations.
            async def evaluate():
                try:
                    return await score_pairs(
                        pairs, questions.questions, eligible, judge, on_score=on_score
                    )
                finally:
                    await judge.close()

            scores = asyncio.run(evaluate())
            report = build_report(
                report_id, questions, profile, pairs, eligible, scores, judge, answer_model
            )
            self.store.put(report)
            with self._lock:
                self._jobs[report_id] = report
            return report
        except Exception:
            self._progress(
                report_id,
                status="failed",
                cause="evaluation interrupted; inspect persisted artifacts",
            )
            raise BenchError(
                "load_failed", "evaluation interrupted; inspect persisted artifacts"
            ) from None

    def run(self, name, corpus, *, sizes=None):
        if sizes is not None and getattr(self.runtime, "supports_sampling", lambda c: False)(
            corpus
        ):
            from bench.eval.curve import CurveEvaluation

            curve = CurveEvaluation(self)
            return curve.execute(*curve.prepare(name, corpus, sizes))
        return self._execute(*self._prepare(name, corpus, sizes))

    def submit(self, name, corpus, *, sizes=None):
        if sizes is not None and getattr(self.runtime, "supports_sampling", lambda c: False)(
            corpus
        ):
            from bench.eval.curve import CurveEvaluation

            curve = CurveEvaluation(self)
            prepared = curve.prepare(name, corpus, sizes)
            self._executor.submit(curve.execute, *prepared)
            return {"report_id": prepared[0], "status_url": f"/bench/reports/{prepared[0]}"}
        prepared = self._prepare(name, corpus, sizes)
        self._executor.submit(self._execute, *prepared)
        return {"report_id": prepared[0], "status_url": f"/bench/reports/{prepared[0]}"}

    def get(self, report_id):
        with self._lock:
            if report_id in self._jobs:
                report = dict(self._jobs[report_id])
                child = self._jobs.get(report.get("active_report_id"))
                if report["status"] == "running" and child is not None:
                    done = len(report["child_report_ids"])
                    arms_per_size = report["total"] // len(report["sizes"])
                    scores_per_size = report["scores_total"] // len(report["sizes"])
                    report.update(
                        phase=child.get("phase", "scoring"),
                        completed=done * arms_per_size
                        + child.get("completed", child.get("question_count", 0) * 2),
                        scores_completed=done * scores_per_size
                        + child.get("scores_completed", len(child.get("scores", []))),
                    )
                return report
        report = self.store.get(report_id)
        if report["status"] == "running":
            return {
                **report,
                "status": "interrupted",
                "cause": "job is not running in this process",
            }
        return report

    def close(self):
        self._executor.shutdown(wait=True)
