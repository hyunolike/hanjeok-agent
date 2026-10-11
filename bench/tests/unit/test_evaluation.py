import json
from dataclasses import replace
from threading import Event

import pytest
import yaml

from bench.answer.pipeline import AnswerPipeline
from bench.graph.query import Passage
from bench.runtime import BenchError


class Runtime:
    model_settings = {"name": "fake", "temperature": 0, "max_tokens": 800}
    embedder = None

    def __init__(self):
        self.calls = []
        self.generation = "generation"

    def corpus_context(self, corpus):
        return {
            "corpus": corpus,
            "corpus_revision": "rev",
            "corpus_generation": "generation",
            "corpus_size": 2,
            "known_paths": {"a.md", "b.md"},
        }

    def ask(self, question, corpus, strategy):
        self.calls.append((question, strategy))
        if question == "failure":
            raise BenchError("load_failed", "provider unavailable")

        class Model:
            def complete(self, system, user, **kwargs):
                from bench.answer.pipeline import ModelReply

                if question == "unsupported":
                    return ModelReply('{"outcome":"no_grounds","answer":null,"citations":[]}', 5, 2)
                return ModelReply(
                    '{"outcome":"answered","answer":"Alpha fact","citations":["a.md"]}', 5, 2
                )

        passages = [Passage("a.md", "a.md#0", "Alpha fact", "A", {"policy": "opaque"})]
        if strategy == "whole":
            passages.append(Passage("b.md", "b.md#0", "Other fact", "B"))
        result = AnswerPipeline(lambda c, q: passages, Model()).ask(
            question, corpus, "rev", {"a.md", "b.md"}
        )
        return replace(result, corpus_size=2, corpus_generation=self.generation)


class Judge:
    settings = {"name": "judge", "temperature": 0, "ragas_version": "test"}
    usage = {"model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def __init__(self):
        self.calls = []

    async def score(self, metric, **kwargs):
        self.calls.append((metric, kwargs))
        if metric == "answer_relevancy" and kwargs["user_input"] == "judge failure":
            raise RuntimeError("secret provider body")
        return 0.8

    async def close(self):
        pass


def service(tmp_path, rows=None, runtime=None, judge=None):
    from bench.eval.questions import QuestionSetLoader
    from bench.eval.service import EvaluationService

    root = tmp_path / "questions"
    root.mkdir(parents=True)
    base = {
        "id": "q1",
        "question": "supported",
        "kind": "single_doc",
        "reference_docs": ["a.md"],
        "must_contain": ["Alpha fact"],
        "corpus": "third",
    }
    root.joinpath("sample.yaml").write_text(
        yaml.safe_dump({"id": "sample", "questions": rows or [base]})
    )
    judge = judge or Judge()
    return (
        EvaluationService(
            runtime or Runtime(),
            QuestionSetLoader(root),
            tmp_path / "runs",
            tmp_path / "reports",
            judge_factory=lambda: judge,
        ),
        judge,
        base,
    )


def test_full_report_persists_provenance_n_kind_and_whole_not_applicable(tmp_path):
    svc, judge, _ = service(tmp_path)
    report = svc.run("sample", "third")
    assert report["status"] == "completed"
    assert report["corpus_revision"] == "rev"
    assert report["corpus_size"] == 2
    assert report["question_set_revision"].startswith("sha256:")
    assert report["judge_model"] == judge.settings
    assert report["strategies"]["whole"]["metrics"]["faithfulness"]["n"] == 1
    assert report["strategies"]["graph"]["by_kind"]["single_doc"]["faithfulness"]["value"] == 0.8
    for strategy in report["strategies"].values():
        assert strategy["outcomes"] == {"answered": 1}
    for name in ("context_precision", "context_recall"):
        metric = report["strategies"]["whole"]["metrics"][name]
        assert metric["value"] is None and metric["n"] == 0
        assert metric["status"] == "not_applicable" and metric["reason"]
    faith = [args for metric, args in judge.calls if metric == "faithfulness"]
    assert len(faith) == 2
    assert all(len(args["retrieved_contexts"]) == 1 for args in faith)
    assert all("opaque" in args["retrieved_contexts"][0] for args in faith)
    assert svc.get(report["report_id"]) == report
    assert len((tmp_path / "runs" / f"{report['report_id']}.jsonl").read_text().splitlines()) == 2
    assert (
        len((tmp_path / "runs" / f"{report['report_id']}.scores.jsonl").read_text().splitlines())
        == 8
    )
    svc.close()


def test_failed_arms_continue_and_declines_are_not_zero_scores(tmp_path):
    rows = [
        dict(
            id=f"q{i}",
            question=question,
            kind="single_doc",
            reference_docs=["a.md"],
            must_contain=["Alpha fact"],
            corpus="third",
        )
        for i, question in enumerate(["failure", "judge failure", "supported"])
    ]
    rows.append(
        dict(
            id="q4",
            question="unsupported",
            kind="unanswerable",
            reference_docs=[],
            must_contain=[],
            corpus="third",
        )
    )
    svc, judge, _ = service(tmp_path, rows)
    report = svc.run("sample", "third")
    assert len(svc.runtime.calls) == 8
    assert report["included_pairs"] == 3 and report["excluded_pairs"] == 1
    for strategy in report["strategies"].values():
        assert strategy["outcomes"] == {"load_failed": 1, "answered": 2, "no_grounds": 1}
        assert strategy["metrics"]["faithfulness"]["n"] == 2
        assert strategy["metrics"]["answer_relevancy"]["n"] == 1
        assert strategy["metrics"]["answer_relevancy"]["failed"] == 1
        assert strategy["abstention"]["unanswerable_accuracy"] == 1
        assert strategy["abstention"]["unanswerable_total"] == 1
        assert strategy["by_kind"]["unanswerable"]["faithfulness"]["value"] is None
    assert "secret provider" not in json.dumps(report)
    svc.close()


def test_missing_reference_and_unsupported_size_fail_before_calls(tmp_path):
    svc, judge, _ = service(
        tmp_path,
        [
            dict(
                id="q",
                question="supported",
                kind="single_doc",
                reference_docs=["missing.md"],
                must_contain=["fact"],
                corpus="third",
            )
        ],
    )
    with pytest.raises(BenchError):
        svc.run("sample", "third")
    assert svc.runtime.calls == [] and judge.calls == []
    svc.close()
    svc, judge, _ = service(tmp_path / "other")
    with pytest.raises(BenchError):
        svc.run("sample", "third", sizes=[1])
    assert svc.runtime.calls == []
    svc.close()


def test_changed_corpus_excludes_pairs_and_never_scores_them(tmp_path):
    runtime = Runtime()
    runtime.generation = "changed"
    svc, judge, _ = service(tmp_path, runtime=runtime)
    report = svc.run("sample", "third")
    assert report["included_pairs"] == 0 and report["excluded_pairs"] == 1
    assert judge.calls == []
    assert report["strategies"]["whole"]["metrics"]["faithfulness"]["n"] == 0
    svc.close()


def test_background_progress_and_restart_loaded_report(tmp_path):
    entered, release = Event(), Event()
    runtime = Runtime()
    original = runtime.ask

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    runtime.ask = blocked
    svc, judge, _ = service(tmp_path, runtime=runtime)
    job = svc.submit("sample", "third")
    assert entered.wait(5)
    progress = svc.get(job["report_id"])
    assert progress["status"] == "running" and progress["total"] == 2
    release.set()
    svc.close()
    report = svc.get(job["report_id"])
    from bench.eval.service import ReportStore

    assert ReportStore(tmp_path / "reports").get(job["report_id"]) == report
    with pytest.raises(BenchError):
        svc.get("../secret")


def test_nonfinite_judge_values_are_failed_not_json_nan(tmp_path):
    judge = Judge()

    async def nan(*args, **kwargs):
        return float("nan")

    judge.score = nan
    svc, _, _ = service(tmp_path, judge=judge)
    report = svc.run("sample", "third")
    assert report["strategies"]["whole"]["metrics"]["faithfulness"]["failed"] == 1
    assert report["strategies"]["whole"]["metrics"]["faithfulness"]["value"] is None
    json.dumps(report, allow_nan=False)
    svc.close()


def test_repeatability_requires_same_profile_and_sample_ids():
    from bench.eval.score import compare_reports

    basic = {
        "report_id": "one",
        "corpus_revision": "rev",
        "corpus_generation": "g",
        "corpus_size": 2,
        "question_set_revision": "qrev",
        "judge_model": {},
        "answer_model": {},
        "scoring_policy": {},
        "strategies": {},
        "scores": [],
    }
    other = {**basic, "report_id": "two", "corpus_generation": "new"}
    assert compare_reports(basic, other)["comparable"] is False
    score = {
        "strategy": "whole",
        "metric": "faithfulness",
        "kind": "single_doc",
        "question_id": "q1",
        "status": "ok",
        "value": 0.8,
    }
    basic["scores"] = [score]
    other = {**basic, "report_id": "two", "scores": [{**score, "value": 0.9}]}
    comparison = compare_reports(basic, other)
    assert comparison["comparable"] and comparison["passes"] is False
    assert comparison["max_delta"] == pytest.approx(0.1)
    other["scores"] = [{**score, "question_id": "q2"}]
    assert compare_reports(basic, other)["comparable"] is False
