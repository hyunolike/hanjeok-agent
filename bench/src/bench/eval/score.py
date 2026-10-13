"""Applicable RAGAS observations, explicit denominators and repeatability evidence."""

import asyncio
import json
import math
from collections import Counter
from datetime import UTC, datetime
from statistics import mean

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
KINDS = ("single_doc", "multi_doc", "unanswerable")
POLICY = {
    "faithfulness_context": "actually supplied passages from cited documents only, including attrs",
    "retrieval_context": "all actually supplied passages, in supplied order",
    "reference": "question must_contain factual clauses joined with newlines",
    "declines": "no numeric answer scores; retrieval scores only when reference and contexts exist",
    "eligible": "both arms normal, shared inputs equal, frozen corpus and answer model match",
    "judge_concurrency": 4,
    "metric_timeout_seconds": 600,
}
WHOLE_REASON = "whole supplies the complete corpus and performs no selective retrieval"


def contexts(run, *, cited_only=False):
    # Use exactly the answer prompt payload, not enriched run telemetry.
    supplied = json.loads(run.inputs["user"])["supplied"] if run.inputs else run.supplied
    return [
        json.dumps(p, ensure_ascii=False, sort_keys=True)
        for p in supplied
        if not cited_only or p["doc"] in run.cited_paths
    ]


async def score_pairs(pairs, questions, eligible, judge, *, on_score):
    semaphore = asyncio.Semaphore(POLICY["judge_concurrency"])
    tasks = []

    def cancel_siblings():
        current = asyncio.current_task()
        for task in tasks:
            if task is not current:
                task.cancel()

    async def observation(run, question, eligible, metric):
        row = {
            "run_id": run.run_id,
            "question_id": question.id,
            "kind": question.kind,
            "strategy": run.strategy,
            "metric": metric,
            "value": None,
            "status": "skipped",
            "reason": None,
        }
        kwargs = {"user_input": question.question}
        if run.strategy == "whole" and metric.startswith("context_"):
            row.update(status="not_applicable", reason=WHOLE_REASON)
        elif not eligible:
            row["reason"] = "pair excluded from the frozen comparison"
        elif metric in ("faithfulness", "answer_relevancy") and run.outcome != "answered":
            row["reason"] = "answer declined; no response to judge"
        elif metric.startswith("context_") and not question.must_contain:
            row.update(
                status="not_applicable", reason="unsupported question has no reference claims"
            )
        else:
            if metric == "faithfulness":
                kwargs.update(
                    response=run.answer, retrieved_contexts=contexts(run, cited_only=True)
                )
            elif metric == "answer_relevancy":
                kwargs["response"] = run.answer
            else:
                kwargs.update(
                    reference="\n".join(question.must_contain), retrieved_contexts=contexts(run)
                )
            if metric != "answer_relevancy" and not kwargs["retrieved_contexts"]:
                row["reason"] = "no supplied contexts to judge"
            else:
                try:
                    async with semaphore:
                        value = float(
                            await asyncio.wait_for(
                                judge.score(metric, **kwargs), POLICY["metric_timeout_seconds"]
                            )
                        )
                    lower = -1 if metric == "answer_relevancy" else 0
                    if not math.isfinite(value) or not lower <= value <= 1:
                        raise ValueError("invalid metric value")
                    row.update(value=value, status="ok")
                except Exception:
                    row.update(status="failed", reason="judge unavailable or invalid metric result")
        try:
            on_score(row)
        except BaseException:
            # Cancel immediately inside the failing observation. Waiting until
            # gather propagates allows other ready tasks to start more calls.
            cancel_siblings()
            raise
        return row

    tasks = [
        asyncio.create_task(observation(run, question, ok, metric))
        for pair, question, ok in zip(pairs, questions, eligible, strict=True)
        for run in (pair.whole, pair.graph)
        for metric in METRICS
    ]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        cancel_siblings()
        # Let every in-flight request unwind before the service closes its
        # client or reports failure; no detached judge work may survive.
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def aggregate(rows, strategy, metric):
    chosen = [r for r in rows if r["strategy"] == strategy and r["metric"] == metric]
    values = [r["value"] for r in chosen if r["status"] == "ok"]
    result = {
        "value": mean(values) if values else None,
        "n": len(values),
        "total": len(chosen),
        "failed": sum(r["status"] == "failed" for r in chosen),
        "skipped": sum(r["status"] == "skipped" for r in chosen),
        "not_applicable": sum(r["status"] == "not_applicable" for r in chosen),
        "status": "ok" if values else "unavailable",
        "reason": None,
    }
    if strategy == "whole" and metric.startswith("context_"):
        result.update(status="not_applicable", reason=WHOLE_REASON)
    elif not values:
        result["reason"] = "no successfully scored samples; see observations for causes"
    return result


def build_report(report_id, question_set, profile, pairs, eligible, scores, judge, answer_model):
    strategies = {}
    for strategy in ("whole", "graph"):
        runs = [getattr(p, strategy) for p in pairs]
        unsupported = [
            (r, q)
            for r, q, ok in zip(runs, question_set.questions, eligible, strict=True)
            if q.kind == "unanswerable"
        ]
        correct = sum(
            r.outcome == "no_grounds" and ok
            for r, q, ok in zip(runs, question_set.questions, eligible, strict=True)
            if q.kind == "unanswerable"
        )
        strategies[strategy] = {
            "outcomes": dict(Counter(r.outcome for r in runs)),
            "attempted": len(runs),
            "metrics": {m: aggregate(scores, strategy, m) for m in METRICS},
            "by_kind": {
                kind: {
                    m: aggregate([s for s in scores if s["kind"] == kind], strategy, m)
                    for m in METRICS
                }
                for kind in KINDS
            },
            "abstention": {
                "unanswerable_correct": correct,
                "unanswerable_total": len(unsupported),
                "unanswerable_accuracy": correct / len(unsupported) if unsupported else None,
            },
            "answer_usage": {
                key: sum(getattr(r, key) for r in runs)
                for key in ("model_calls", "prompt_tokens", "completion_tokens", "elapsed_ms")
            },
        }
    return {
        "report_id": report_id,
        "status": "completed",
        "timestamp": datetime.now(UTC).isoformat(),
        "corpus": profile["corpus"],
        "corpus_revision": profile["corpus_revision"],
        "corpus_generation": profile["corpus_generation"],
        "corpus_size": profile["corpus_size"],
        "question_set": question_set.id,
        "question_set_revision": question_set.revision,
        "question_count": len(question_set.questions),
        "answer_model": answer_model,
        "judge_model": judge.settings,
        "judge_usage": dict(judge.usage),
        "judge_errors": list(getattr(judge, "errors", [])),
        "scoring_policy": POLICY,
        "valid_pairs": sum(p.valid for p in pairs),
        "included_pairs": sum(eligible),
        "excluded_pairs": len(pairs) - sum(eligible),
        "pairs": [
            {
                "pair_id": p.pair_id,
                "question_id": q.id,
                "included": ok,
                "cause": None if ok else p.cause or "failed arm or frozen profile mismatch",
            }
            for p, q, ok in zip(pairs, question_set.questions, eligible, strict=True)
        ],
        "strategies": strategies,
        "scores": scores,
        "artifacts": {
            "runs": f"{report_id}.jsonl",
            "pairs": f"{report_id}.pairs.jsonl",
            "scores": f"{report_id}.scores.jsonl",
        },
    }


def compare_reports(left, right, *, tolerance=0.05):
    result = {
        "reports": [left["report_id"], right["report_id"]],
        "tolerance": tolerance,
        "comparable": False,
        "passes": None,
        "max_delta": None,
        "deltas": [],
        "reason": None,
    }
    fields = (
        "corpus_revision",
        "corpus_generation",
        "corpus_size",
        "question_set_revision",
        "judge_model",
        "answer_model",
        "scoring_policy",
    )
    if any(left[k] != right[k] for k in fields):
        result["reason"] = "report profiles differ"
        return result

    def observations(report):
        return {
            (s["strategy"], s["metric"], s["kind"], s["question_id"]): s for s in report["scores"]
        }

    lrows, rrows = observations(left), observations(right)
    if (
        not lrows
        or lrows.keys() != rrows.keys()
        or any(
            lrows[k]["status"] != rrows[k]["status"] or lrows[k]["status"] == "failed"
            for k in lrows
        )
    ):
        result["reason"] = "scored sample membership differs, is empty, or contains judge failures"
        return result
    for strategy in ("whole", "graph"):
        for kind in ("all", *KINDS):
            for metric in METRICS:
                keys = [
                    k
                    for k in lrows
                    if k[0] == strategy
                    and k[1] == metric
                    and (kind == "all" or k[2] == kind)
                    and lrows[k]["status"] == "ok"
                ]
                if keys:
                    a, b = (
                        mean(lrows[k]["value"] for k in keys),
                        mean(rrows[k]["value"] for k in keys),
                    )
                    result["deltas"].append(
                        {
                            "strategy": strategy,
                            "kind": kind,
                            "metric": metric,
                            "left": a,
                            "right": b,
                            "n": len(keys),
                            "delta": abs(a - b),
                        }
                    )
    maximum = max((d["delta"] for d in result["deltas"]), default=None)
    result.update(
        comparable=maximum is not None,
        max_delta=maximum,
        passes=maximum < tolerance if maximum is not None else None,
    )
    return result
