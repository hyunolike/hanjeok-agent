"""Turn run records into the report the evaluation page shows.

Three kinds of number, kept apart because they rest on different things:

- **Judged** (faithfulness, answer relevancy, context precision and recall):
  RAGAS, through the bench's judge. The judge is the same hosted model that
  answers, which is why the next two exist.
- **Counted from ids** (record precision and recall): what a question's lookups
  fetched against the ids the question is known to need. No model involved.
- **Counted by rule** (forbidden behaviours): `guide.forbidden`.

Every score carries how many questions it was computed over and how many it
could have been. A question that could not be scored is "not scored" with a
reason; it is never a zero (spec FR-027).
"""

from __future__ import annotations

import asyncio
import math
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from statistics import mean

from guide.eval.questions import KINDS, QuestionSet
from guide.forbidden import BEHAVIOURS

JUDGED = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
COUNTED = ("id_precision", "id_recall")
METRICS = (*JUDGED, *COUNTED)
# One metric makes several requests and each may wait out a rate limit.
JUDGE_TIMEOUT_S = 3600
JUDGE_CONCURRENCY = 2

NOT_ANSWERABLE = "답하지 않는 것이 정답인 질문이라 점수를 매기지 않습니다."
NOT_ANSWERED = "답이 나오지 않아 판정할 글이 없습니다."
NO_JUDGE = "판정 모델을 돌리지 않은 평가입니다."
JUDGE_FAILED = "판정 모델 호출이 실패했거나 쓸 수 없는 값을 돌려주었습니다."
NO_REFERENCE = "이 질문에 필요한 근거를 어느 방식도 가져오지 못해 기준 글을 만들 수 없습니다."
NO_CONTEXT = "건넨 근거가 없습니다."


def _score(value=None, status="ok", reason=None) -> dict:
    return {"value": value, "status": status, "reason": reason}


def id_scores(record: dict) -> dict[str, dict]:
    """Precision and recall of what was fetched against what was needed."""
    needs = set(record["needs"])
    if not needs:
        return {
            metric: _score(status="not_applicable", reason=NOT_ANSWERABLE) for metric in COUNTED
        }
    fetched = set(record["fetched"])
    hit = len(needs & fetched)
    return {
        # Nothing fetched is a precision that cannot be computed, not a zero.
        "id_precision": _score(hit / len(fetched))
        if fetched
        else _score(status="unavailable", reason=NO_CONTEXT),
        "id_recall": _score(hit / len(needs)),
    }


def _reference(question_id: str, records: Sequence[dict]) -> str | None:
    """The text of the passages a question needs, from whichever strategy
    fetched them. Both read the same Hanjeok responses and the same graph, so a
    passage has one text regardless of who fetched it."""
    mine = [record for record in records if record["question_id"] == question_id]
    texts = {p["id"]: p["text"] for record in mine for p in record["passages"]}
    needs = mine[0]["needs"]
    if not needs or any(need not in texts for need in needs):
        return None
    return "\n".join(texts[need] for need in needs)


async def judged_scores(records: Sequence[dict], judge) -> dict[str, dict[str, dict]]:
    """run_id -> metric -> score, for the four judged metrics."""
    out: dict[str, dict[str, dict]] = {record["run_id"]: {} for record in records}
    semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)

    async def one(record: dict, metric: str) -> None:
        cell = out[record["run_id"]]
        if not record["needs"]:
            cell[metric] = _score(status="not_applicable", reason=NOT_ANSWERABLE)
            return
        if judge is None:
            cell[metric] = _score(status="unavailable", reason=NO_JUDGE)
            return
        kwargs = {"user_input": record["question"]}
        if metric in ("faithfulness", "answer_relevancy"):
            if record["outcome"] != "answered":
                cell[metric] = _score(status="unavailable", reason=NOT_ANSWERED)
                return
            kwargs["response"] = record["answer"]
            if metric == "faithfulness":
                # Judged against what the answer cited, not everything fetched:
                # the claim under test is "supported by what it points at".
                cited = [p["text"] for p in record["passages"] if p["id"] in record["citations"]]
                kwargs["retrieved_contexts"] = cited
        else:
            reference = _reference(record["question_id"], records)
            if reference is None:
                cell[metric] = _score(status="unavailable", reason=NO_REFERENCE)
                return
            kwargs.update(
                reference=reference, retrieved_contexts=[p["text"] for p in record["passages"]]
            )
        if metric != "answer_relevancy" and not kwargs["retrieved_contexts"]:
            cell[metric] = _score(status="unavailable", reason=NO_CONTEXT)
            return
        try:
            async with semaphore:
                value = float(
                    await asyncio.wait_for(judge.score(metric, **kwargs), JUDGE_TIMEOUT_S)
                )
            if not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError("invalid metric value")
            # Answer relevancy is a cosine and can dip below zero; the page
            # shows scores between 0 and 1.
            cell[metric] = _score(min(1.0, max(0.0, value)))
        except Exception:
            cell[metric] = _score(status="unavailable", reason=JUDGE_FAILED)

    await asyncio.gather(*(one(record, metric) for record in records for metric in JUDGED))
    return out


def aggregate(scores: Sequence[dict]) -> dict:
    applicable = [score for score in scores if score["status"] != "not_applicable"]
    if not applicable:
        reason = scores[0]["reason"] if scores else None
        return {
            "value": None,
            "n": 0,
            "total": len(scores),
            "status": "not_applicable",
            "reason": reason,
        }
    values = [score["value"] for score in applicable if score["status"] == "ok"]
    if not values:
        reasons = Counter(score["reason"] for score in applicable)
        return {
            "value": None,
            "n": 0,
            "total": len(applicable),
            "status": "unavailable",
            "reason": reasons.most_common(1)[0][0],
        }
    return {
        "value": round(mean(values), 4),
        "n": len(values),
        "total": len(applicable),
        "status": "ok",
        "reason": None,
    }


def build(
    report_id: str,
    question_set: QuestionSet,
    records: Sequence[dict],
    scores: dict[str, dict[str, dict]],
    *,
    answer_model: str,
    judge_model: str,
    generation: str,
    export_sha256: str,
    export_as_of: str,
    live_recorded_at: str,
    limitations: Sequence[str],
) -> tuple[dict, dict[str, dict]]:
    """The report, and one sample per question keyed by question id."""
    strategies = {}
    arms = list(dict.fromkeys(record["strategy"] for record in records))
    for strategy in arms:
        mine = [record for record in records if record["strategy"] == strategy]
        unsupported = [record for record in mine if record["kind"] == "unsupported"]
        strategies[strategy] = {
            "attempted": len(mine),
            "outcomes": dict(Counter(record["outcome"] for record in mine)),
            "metrics": {m: aggregate([scores[r["run_id"]][m] for r in mine]) for m in METRICS},
            "by_kind": {
                kind: {
                    m: aggregate([scores[r["run_id"]][m] for r in mine if r["kind"] == kind])
                    for m in METRICS
                }
                for kind in KINDS
            },
            "forbidden": {
                behaviour: {
                    "runs": len(mine),
                    "occurrences": sum(behaviour in r["forbidden"] for r in mine),
                }
                for behaviour in BEHAVIOURS
            },
            "abstention": {
                # Declining and finding no grounds are both "did not answer".
                "unanswerable_correct": sum(
                    r["outcome"] in ("declined", "no_grounds") for r in unsupported
                ),
                "unanswerable_total": len(unsupported),
            },
            "answer_usage": {
                key: sum(record[key] for record in mine)
                for key in ("model_calls", "prompt_tokens", "completion_tokens", "elapsed_ms")
            },
        }

    order = list(dict.fromkeys(record["question_id"] for record in records))
    first = {qid: next(r for r in records if r["question_id"] == qid) for qid in order}
    report = {
        "report_id": report_id,
        "status": "completed",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "question_set": question_set.id,
        "question_set_revision": question_set.revision,
        "question_count": len(order),
        "answer_model": answer_model,
        "judge_model": judge_model,
        "generation": generation,
        "export_sha256": export_sha256,
        "export_as_of": export_as_of,
        "live_recorded_at": live_recorded_at,
        "strategies": strategies,
        "questions": [
            {"question_id": qid, "kind": first[qid]["kind"], "question": first[qid]["question"]}
            for qid in order
        ],
        "limitations": list(limitations),
    }
    samples = {
        qid: {
            "report_id": report_id,
            "question_id": qid,
            "kind": first[qid]["kind"],
            "question": first[qid]["question"],
            "strategies": {
                record["strategy"]: {
                    "outcome": record["outcome"],
                    "cause": record["cause"],
                    "answer": record["answer"],
                    "citations": record["citations"],
                    "steps": record["steps"],
                    "passages": [{"id": p["id"], "text": p["text"]} for p in record["passages"]],
                    "scores": scores[record["run_id"]],
                    "forbidden": record["forbidden"],
                }
                for record in records
                if record["question_id"] == qid
            },
        }
        for qid in order
    }
    return report, samples


def score_all(records: Sequence[dict], judge) -> dict[str, dict[str, dict]]:
    scores = asyncio.run(judged_scores(records, judge))
    for record in records:
        scores[record["run_id"]].update(id_scores(record))
    return scores
