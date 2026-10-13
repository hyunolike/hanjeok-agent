"""Multi-size evaluations retain independent frozen reports and exact samples."""

import json
from datetime import UTC, datetime
from statistics import mean
from uuid import uuid4

from bench.runtime import BenchError


def by_size(report, runs):
    strategies = {}
    for strategy in ("whole", "graph"):
        arms = [row for row in runs if row["strategy"] == strategy]
        measured = [row["prompt_tokens"] for row in arms if row["prompt_tokens"] > 0]
        supplied_bytes = [
            len(
                json.dumps(
                    json.loads(row["inputs"]["user"])["supplied"], ensure_ascii=False
                ).encode()
            )
            for row in arms
            if row["inputs"] is not None
        ]
        strategies[strategy] = {
            **report["strategies"][strategy],
            "prompt_tokens": {
                "total": sum(measured),
                "mean": mean(measured) if measured else None,
                "n": len(measured),
                "unmeasured": len(arms) - len(measured),
                "scope": "actual provider input usage including shared prompt/schema; all attempts",
            },
            "supplied_bytes": {
                "mean": mean(supplied_bytes) if supplied_bytes else None,
                "n": len(supplied_bytes),
                "scope": "exact selected supplied JSON UTF-8 bytes, including unsent contexts",
            },
        }
    return {
        "report_id": report["report_id"],
        "corpus_size": report["corpus_size"],
        "corpus_revision": report["corpus_revision"],
        "corpus_generation": report["corpus_generation"],
        "included_pairs": report["included_pairs"],
        "excluded_pairs": report["excluded_pairs"],
        "strategies": strategies,
    }


class CurveEvaluation:
    def __init__(self, service):
        self.service = service

    def prepare(self, name, corpus, sizes):
        svc = self.service
        questions = svc.questions.load(name)
        references = {path for question in questions.questions for path in question.reference_docs}
        samples = svc.runtime.prepare_samples(corpus, sizes, references)
        if len(samples) != len(sizes):
            raise BenchError("load_failed", "incomplete sample plan", 409)
        for size, sample in zip(sizes, samples, strict=True):
            if len(sample.loaded.docs) != size or any(
                d.corpus != corpus for d in sample.loaded.docs
            ):
                raise BenchError("load_failed", "sample size or corpus mismatch", 409)
            questions.validate_corpus(corpus, {d.path for d in sample.loaded.docs})
        model = svc.runtime.model_settings
        report_id = str(uuid4())
        progress = {
            "report_id": report_id,
            "report_type": "size_curve",
            "status": "running",
            "phase": "rebuilding",
            "sizes": sizes,
            "corpus": corpus,
            "completed": 0,
            "total": 2 * len(sizes) * len(questions.questions),
            "scores_completed": 0,
            "scores_total": 8 * len(sizes) * len(questions.questions),
            "child_report_ids": [],
            "active_report_id": None,
        }
        svc.store.put(progress)
        with svc._lock:
            svc._jobs[report_id] = progress
        return report_id, questions, corpus, samples, model

    def execute(self, report_id, questions, corpus, samples, model):
        svc = self.service
        children, rows = [], []
        try:
            with svc.runtime.evaluation_scope():
                for sample in samples:
                    if svc.runtime.model_settings != model:
                        raise BenchError("load_failed", "answer profile changed during curve")
                    svc._progress(report_id, phase="rebuilding", active_report_id=None)
                    svc.runtime.rebuild_loaded(corpus, sample.loaded)
                    prepared = svc._prepare(questions.id, corpus, None, questions=questions)
                    profile = prepared[2]
                    if profile["corpus_revision"] != sample.loaded.revision or profile[
                        "corpus_size"
                    ] != len(sample.loaded.docs):
                        raise BenchError(
                            "load_failed", "loaded sample does not match prepared snapshot"
                        )
                    svc._progress(report_id, active_report_id=prepared[0])
                    child = svc._execute(*prepared)
                    children.append(child)
                    raw = svc.runs_root / child["artifacts"]["runs"]
                    runs = [json.loads(line) for line in raw.read_text().splitlines()]
                    rows.append(by_size(child, runs))
                    svc._progress(
                        report_id,
                        child_report_ids=[c["report_id"] for c in children],
                        active_report_id=None,
                        completed=len(children) * 2 * len(questions.questions),
                        scores_completed=len(children) * 8 * len(questions.questions),
                    )
            report = {
                "report_id": report_id,
                "report_type": "size_curve",
                "status": "completed",
                "timestamp": datetime.now(UTC).isoformat(),
                "corpus": corpus,
                "question_set": questions.id,
                "question_set_revision": questions.revision,
                "question_count": len(questions.questions),
                "answer_model": model,
                "child_report_ids": [c["report_id"] for c in children],
                "sampling": [s.manifest for s in samples],
                "by_size": rows,
                "measurement": (
                    "paired quality only; failures retained; prompt tokens are provider usage, "
                    "not a supplied-only tokenizer count"
                ),
            }
            svc.store.put(report)
            with svc._lock:
                svc._jobs[report_id] = report
            return report
        except Exception:
            svc._progress(
                report_id,
                status="failed",
                cause="size evaluation interrupted; completed child reports retained",
            )
            raise BenchError(
                "load_failed", "size evaluation interrupted; inspect saved reports"
            ) from None
