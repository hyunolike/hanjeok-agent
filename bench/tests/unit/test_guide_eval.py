"""Evaluation machinery with a scripted model and a fake judge. No quota spent."""

from __future__ import annotations

import json

import pytest
from tests.guide_fakes import (
    TODAY,
    ExportPlaces,
    FakePolicy,
    ScriptedModel,
    action,
    answer,
    replay_live,
)

from guide.eval.questions import load
from guide.eval.report import METRICS, aggregate, id_scores
from guide.eval.run import STRATEGIES, SharedLive, run
from guide.eval.service import evaluate
from guide.eval.store import ReportStore
from guide.live import LiveClient, LiveError

SET = "questions/hanjeok-synthetic-v1.yaml"


class Obliging:
    """Answers any question the same way under any strategy: look up the first
    thing it needs, then cite everything fetched. Lets the two arms differ only
    where the strategy makes them differ."""

    settings = {"name": "obliging"}

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.usage = {"model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def decide(self, system, user, schema, *, timeout):
        self.calls.append({"system": system, "user": user, "schema": schema})
        self.usage["model_calls"] += 1
        self.usage["prompt_tokens"] += 100
        self.usage["completion_tokens"] += 10
        actions = schema["properties"]["action"]["enum"]
        fetched = [line.split("]")[0][1:] for line in user.splitlines() if line.startswith("[")]
        if (
            "related_places" in actions
            and "이어진" in user.split("쓸 수 있는 조회")[0]
            and not any(f.startswith("hanjeok:related/") for f in fetched)
        ):
            place = next(f for f in fetched if f.startswith("hanjeok:place/"))
            return action("related_places", place_id=int(place.rsplit("/", 1)[1]))
        if "policy" in actions and not fetched:
            return action("policy", text="기준")
        return answer("가진 근거로 답합니다.", *fetched[:3])


class FakeJudge:
    settings = {"name": "fake-judge"}

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.seen: list[tuple[str, dict]] = []
        self._fail_on = fail_on

    async def score(self, metric, **kwargs):
        self.seen.append((metric, kwargs))
        if metric == self._fail_on:
            raise RuntimeError("judge down")
        return 0.5


def do(tmp_path, *, judge=None, model=None, **kwargs):
    store = ReportStore(tmp_path / "reports")
    report = evaluate(
        SET,
        model=model or Obliging(),
        places=ExportPlaces(),
        policy=FakePolicy(),
        live=replay_live(),
        judge=judge,
        store=store,
        runs_dir=tmp_path / "runs",
        generation="gen-test",
        export_sha256="a" * 64,
        export_as_of="2026-10-13T02:00:00Z",
        export_source="hanjeok-synthetic",
        allow_small=True,
        report_id="r1",
        **kwargs,
    )
    return report, store


def test_both_strategies_answer_every_question_and_the_report_is_stored(tmp_path):
    report, store = do(tmp_path)

    assert set(report["strategies"]) == set(STRATEGIES)
    assert report["question_count"] == 12
    assert all(arm["attempted"] == 12 for arm in report["strategies"].values())
    assert store.get("r1") == report
    assert (report["generation"], report["export_as_of"]) == ("gen-test", "2026-10-13T02:00:00Z")
    # This model never asks Hanjeok anything, so there is no fetch time to
    # report and the run's own time stands in.
    assert report["live_recorded_at"].endswith("Z")
    assert len(report["question_set_revision"]) == 12
    runs = (tmp_path / "runs" / "r1.jsonl").read_text("utf-8").splitlines()
    assert len(runs) == 24
    assert json.loads(runs[0])["export_sha256"] == "a" * 64


def test_every_score_has_its_denominator_and_unanswerable_questions_are_left_out(tmp_path):
    report, _ = do(tmp_path, judge=FakeJudge())

    for arm in report["strategies"].values():
        for metric in METRICS:
            cell = arm["metrics"][metric]
            assert cell["total"] == 10, "the two unsupported questions are not applicable"
            assert cell["n"] <= cell["total"]
            assert (cell["status"] == "ok") == (cell["value"] is not None)
        for metric in METRICS:
            assert arm["by_kind"]["unsupported"][metric]["status"] == "not_applicable"
        assert arm["abstention"] == {"unanswerable_correct": 2, "unanswerable_total": 2}


def test_without_a_judge_judged_metrics_are_not_scored_rather_than_zero(tmp_path):
    report, _ = do(tmp_path)

    cell = report["strategies"]["graph"]["metrics"]["faithfulness"]
    assert (cell["value"], cell["status"], cell["n"], cell["total"]) == (None, "unavailable", 0, 10)
    assert "돌리지 않은" in cell["reason"]
    assert report["strategies"]["graph"]["metrics"]["id_recall"]["status"] == "ok"
    assert report["judge_model"] == "(돌리지 않음)"
    assert any("판정 모델을 돌리지 않았습니다" in line for line in report["limitations"])


def test_a_judge_failure_leaves_that_metric_unscored_and_the_others_intact(tmp_path):
    report, _ = do(tmp_path, judge=FakeJudge(fail_on="faithfulness"))

    arm = report["strategies"]["vector"]["metrics"]
    assert arm["faithfulness"]["status"] == "unavailable" and arm["faithfulness"]["value"] is None
    assert arm["answer_relevancy"]["value"] == 0.5


def test_following_links_is_what_makes_the_linked_place_questions_recallable(tmp_path):
    report, store = do(tmp_path)

    graph = report["strategies"]["graph"]["by_kind"]["multi_place"]["id_recall"]
    vector = report["strategies"]["vector"]["by_kind"]["multi_place"]["id_recall"]
    assert graph["value"] > vector["value"]
    assert graph["n"] == vector["n"] == 2
    sample = store.sample("r1", "q09")
    assert "hanjeok:related/101" in [p["id"] for p in sample["strategies"]["graph"]["passages"]]
    assert "hanjeok:related/101" not in [
        p["id"] for p in sample["strategies"]["vector"]["passages"]
    ]


def test_the_two_arms_are_shown_the_same_first_prompt_except_the_offered_lookups(tmp_path):
    model = Obliging()
    do(tmp_path, model=model)

    runs = [
        json.loads(line)
        for line in (tmp_path / "runs" / "r1.jsonl").read_text("utf-8").splitlines()
    ]
    for question_id in {record["question_id"] for record in runs}:
        vector, graph = (
            next(r for r in runs if r["question_id"] == question_id and r["strategy"] == s)
            for s in STRATEGIES
        )
        if not vector["prompts"]:
            assert not graph["prompts"], "a question declined by rule is declined in both"
            continue
        assert vector["prompts"][0]["system"] == graph["prompts"][0]["system"]
        differing = set(vector["prompts"][0]["user"].splitlines()) ^ set(
            graph["prompts"][0]["user"].splitlines()
        )
        assert (
            all(line.startswith("- related_places(") for line in differing) and len(differing) == 1
        )
        assert vector["question"] == graph["question"]


def test_the_judge_sees_only_cited_passages_for_faithfulness(tmp_path):
    judge = FakeJudge()
    do(tmp_path, judge=judge)

    faithfulness = [kwargs for metric, kwargs in judge.seen if metric == "faithfulness"]
    assert faithfulness and all(
        1 <= len(kwargs["retrieved_contexts"]) <= 3 for kwargs in faithfulness
    )
    assert all(
        "reference" in kwargs for metric, kwargs in judge.seen if metric.startswith("context_")
    )


def test_limitations_say_what_this_run_was(tmp_path):
    report, _ = do(tmp_path)

    text = "\n".join(report["limitations"])
    for phrase in ("가상 내보내기 파일", "12개뿐", "같은 모델", "녹화해 둔 응답"):
        assert phrase in text


def test_a_report_becomes_the_shown_one_only_when_published(tmp_path):
    _, store = do(tmp_path)

    assert store.latest() is None
    assert store.publish("nope") is False
    assert store.publish("r1") is True
    assert store.latest()["report_id"] == "r1"


@pytest.mark.parametrize("report_id", ["../r1", "r1/../../etc", "", "a" * 81, "r 1"])
def test_a_report_id_that_is_not_a_plain_token_is_not_a_report(tmp_path, report_id):
    _, store = do(tmp_path)

    assert store.get(report_id) is None
    assert store.sample(report_id, "q01") is None
    assert store.publish(report_id) is False


def test_hanjeok_is_asked_once_and_a_failure_is_shared_between_the_arms():
    calls = []
    real = replay_live()

    class Counting(LiveClient):
        mode, recording = "replay", None

        def __init__(self) -> None:
            pass

        def today(self):
            return TODAY

        def congestion(self, place_id, day):
            calls.append((place_id, day))
            if place_id == 118:
                raise LiveError("service_unreachable")
            return real.congestion(place_id, day)

    shared = SharedLive(Counting())
    assert shared.congestion(101, "2026-10-17") == shared.congestion(101, "2026-10-17")
    for _ in range(2):
        with pytest.raises(LiveError):
            shared.congestion(118, "2026-10-17")

    assert calls == [(101, "2026-10-17"), (118, "2026-10-17")]
    assert shared.fetched_at() == "2026-10-13T14:20:05Z"


def test_id_scores_and_aggregation():
    record = {"needs": ["a", "b"], "fetched": ["a", "x", "y", "z"]}
    assert id_scores(record)["id_recall"]["value"] == 0.5
    assert id_scores(record)["id_precision"]["value"] == 0.25
    assert id_scores({"needs": ["a"], "fetched": []})["id_precision"]["status"] == "unavailable"
    assert id_scores({"needs": [], "fetched": ["a"]})["id_recall"]["status"] == "not_applicable"

    ok = {"value": 1.0, "status": "ok", "reason": None}
    missing = {"value": None, "status": "unavailable", "reason": "why"}
    skipped = {"value": None, "status": "not_applicable", "reason": "n/a"}
    assert aggregate([ok, missing, skipped]) == {
        "value": 1.0,
        "n": 1,
        "total": 2,
        "status": "ok",
        "reason": None,
    }
    assert aggregate([missing, missing])["reason"] == "why"
    assert aggregate([skipped])["status"] == "not_applicable"


def test_the_runner_takes_the_questions_of_the_day():
    questions = load(SET, minimum=1, minimum_per_kind=0).on(TODAY)[:2]
    model = ScriptedModel(
        action("congestion", place_id=101, date="2026-10-17"),
        answer("매우혼잡 예보입니다.", "hanjeok:congestion/101@2026-10-17"),
    )

    records, _ = run(
        questions[:1],
        model=model,
        places=ExportPlaces(),
        policy=FakePolicy(),
        live=replay_live(),
        today=TODAY,
        strategies=("graph",),
    )

    assert records[0]["question"] == "가람궁은 10월 17일에 얼마나 붐벼?"
    assert records[0]["outcome"] == "answered"
    assert id_scores(records[0])["id_recall"]["value"] == 1.0


def test_waiting_out_a_rate_limit_is_not_charged_to_the_question(tmp_path):
    from guide.eval.run import PatientModel
    from guide.model import ModelFailure

    now = [0.0]
    inner = ScriptedModel(
        ModelFailure("rate_limit"),
        ModelFailure("rate_limit"),
        action("congestion", place_id=101, date="2026-10-17"),
        answer("매우혼잡 예보입니다.", "hanjeok:congestion/101@2026-10-17"),
    )

    def sleep(seconds):
        now[0] += seconds

    patient = PatientModel(inner, waits=(40.0, 40.0), sleep=sleep, clock=lambda: now[0])
    question = load(SET, minimum=1, minimum_per_kind=0).on(TODAY)[0]

    records, _ = run(
        [question],
        model=patient,
        places=ExportPlaces(),
        policy=FakePolicy(),
        live=replay_live(),
        today=TODAY,
        strategies=("graph",),
    )

    # Eighty seconds were spent waiting, more than a question's whole budget.
    assert now[0] == 80.0
    assert records[0]["outcome"] == "answered"
    assert records[0]["rate_limit_waits"] == 2
    assert records[0]["elapsed_ms"] == 0


def test_a_patient_model_still_gives_up_and_passes_other_failures_through():
    from guide.eval.run import PatientModel
    from guide.model import ModelFailure

    always = PatientModel(
        ScriptedModel(*[ModelFailure("rate_limit")] * 3), waits=(1.0, 1.0), sleep=lambda s: None
    )
    with pytest.raises(ModelFailure, match="rate_limit"):
        always.decide("s", "u", {"properties": {"action": {"enum": ["answer"]}}}, timeout=60)

    other = PatientModel(ScriptedModel(ModelFailure("authentication")), sleep=lambda s: None)
    with pytest.raises(ModelFailure, match="authentication"):
        other.decide("s", "u", {"properties": {"action": {"enum": ["answer"]}}}, timeout=60)
    assert other.waits == 0


def test_the_report_and_a_sample_are_the_files_the_frontend_parses(tmp_path):
    """Same idea as the recorded streams: the service must still produce these
    two files and `frontend/src/lib/guide-contract.test.ts` must still parse
    them. `GUIDE_RECORD_STREAMS=1` rewrites them after an intended change."""
    import os
    from pathlib import Path

    report, store = do(tmp_path, judge=FakeJudge(fail_on="context_recall"))
    report = {**report, "timestamp": "2026-10-13T15:10:00Z", "live_recorded_at": "2026-10-13T14:20:05Z"}
    for arm in report["strategies"].values():
        arm["answer_usage"]["elapsed_ms"] = 0
    produced = {"report": report, "sample": store.sample("r1", "q09")}

    directory = Path(__file__).parents[1] / "fixtures" / "guide-report"
    for name, data in produced.items():
        path = directory / f"{name}.json"
        if os.environ.get("GUIDE_RECORD_STREAMS") == "1":
            directory.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
        assert json.loads(path.read_text("utf-8")) == data


def test_the_command_line_path_wraps_the_model_patiently(tmp_path):
    # The `guide eval` wiring passes patient=True; an import missing on that
    # path once made the real run fail after every offline test had passed.
    report, _ = do(tmp_path, patient=True)

    assert report["question_count"] == 12
