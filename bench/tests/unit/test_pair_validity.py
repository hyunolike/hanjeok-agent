import json
from dataclasses import replace

import pytest

from bench.answer.pipeline import AnswerPipeline, ModelReply
from bench.graph.query import Passage
from bench.runtime import BenchError


class FixtureRuntime:
    """Replace only the database boundary; execute the real prompt and gate."""

    model_settings = {"name": "fixture-model", "temperature": 0, "max_tokens": 800}

    def __init__(self, *, revisions=("rev", "rev"), generations=("g", "g"), failure=None):
        self.revisions, self.generations, self.failure = revisions, generations, failure
        self.requests = []

    def ask(self, question, corpus, strategy):
        index = len(self.requests)
        self.requests.append((question, corpus, strategy))
        if index == 0 and self.failure == "load":
            raise BenchError("load_failed", "corpus is not loaded", 409)
        if index == 0 and self.failure == "unexpected":
            raise RuntimeError("private provider details /outside/key")
        rows = [Passage("a.md", "a.md#0", "fact", "A")]
        if strategy == "whole":
            rows.append(Passage("b.md", "b.md#0", "other fact", "B"))

        class Model:
            def complete(self, system, user, **kwargs):
                if index == 0 and self.failure == "model":
                    return ModelReply("", 11, 4, "malformed")
                return ModelReply(
                    '{"outcome":"answered","answer":"fact","citations":["a.md"]}', 30, 5
                )

        model = Model()
        model.failure = self.failure
        result = AnswerPipeline(lambda c, q: rows, model).ask(
            question, corpus, self.revisions[index], {"a.md", "b.md"}
        )
        result = replace(result, corpus_size=2, corpus_generation=self.generations[index])
        if index == 0 and self.failure == "rebuild":
            result = replace(
                result,
                outcome="load_failed",
                answer=None,
                citations=(),
                cause="corpus changed during the request",
            )
            raise BenchError("load_failed", result.cause, 409, result=result)
        return result


def pair(tmp_path, runtime=None):
    from bench.eval.runner import PairRunner

    return PairRunner(runtime or FixtureRuntime(), tmp_path / "runs.jsonl").pair(
        question_id="q1", question="What?", corpus="third"
    )


def test_pair_persists_two_runs_and_audits_only_supplied_difference(tmp_path):
    result = pair(tmp_path)
    assert result.valid and len(result.scoring_runs) == 2
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert len(records) == 2
    assert [r["strategy"] for r in records] == ["whole", "graph"]
    assert all(r["question_id"] == "q1" and r["question"] == "What?" for r in records)
    assert all(r["corpus_size"] == 2 and r["corpus_revision"] == "rev" for r in records)
    assert all(r["model"] == FixtureRuntime.model_settings for r in records)
    assert all(r["prompt_tokens"] == 30 and r["completion_tokens"] == 5 for r in records)
    assert result.diff["shared_equal"] and result.diff["differences"] == ["supplied"]
    assert "fact" in records[0]["inputs"]["user"]
    assert records[0]["supplied"][0]["text"] == "fact"
    assert records[0]["pair_id"] == records[1]["pair_id"]
    saved = json.loads((tmp_path / "runs.pairs.jsonl").read_text())
    assert saved["valid"] is True and saved["pair_id"] == records[0]["pair_id"]


@pytest.mark.parametrize(
    "kwargs,cause",
    [
        ({"revisions": ("old", "new")}, "corpus_revision"),
        ({"generations": ("old", "new")}, "corpus_generation"),
    ],
)
def test_changed_corpus_pair_is_recorded_but_excluded_from_scoring(tmp_path, kwargs, cause):
    result = pair(tmp_path, FixtureRuntime(**kwargs))
    assert not result.valid and result.scoring_runs == ()
    assert cause in result.cause
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 2
    assert json.loads((tmp_path / "runs.pairs.jsonl").read_text())["valid"] is False


@pytest.mark.parametrize(
    "failure,outcome",
    [
        ("load", "load_failed"),
        ("model", "model_failed"),
        ("unexpected", "load_failed"),
        ("rebuild", "load_failed"),
    ],
)
def test_failed_arm_is_retained_and_other_arm_still_runs(tmp_path, failure, outcome):
    result = pair(tmp_path, FixtureRuntime(failure=failure))
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert records[0]["outcome"] == outcome and records[0]["answer"] is None
    assert records[0]["cited_paths"] == [] and records[0]["cause"]
    assert records[1]["outcome"] == "answered"
    assert result.scoring_runs == ()
    assert "private provider" not in (tmp_path / "runs.jsonl").read_text()
    if failure == "model":
        assert records[0]["prompt_tokens"] == 11 and records[0]["completion_tokens"] == 4
    if failure == "rebuild":
        assert records[0]["prompt_tokens"] == 30 and records[0]["corpus_revision"] == "rev"


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", {"name": "different-model"}),
        ("question", "Different question"),
        ("corpus_size", 3),
    ],
)
def test_record_validity_checks_shared_settings_and_question_text(tmp_path, field, value):
    from bench.eval.runner import pair_records

    result = pair(tmp_path)
    graph = replace(result.graph, **{field: value})
    changed = pair_records(result.whole, graph)
    assert not changed.valid and field in changed.cause
    assert changed.scoring_runs == ()


def test_diff_detects_prompt_drift_even_with_identical_revision(tmp_path):
    from bench.eval.runner import pair_records

    result = pair(tmp_path)
    inputs = {**result.graph.inputs, "system": "different instructions"}
    changed = pair_records(result.whole, replace(result.graph, inputs=inputs))
    assert not changed.valid and not changed.diff["shared_equal"]
    assert "system" in changed.diff["differences"]


def test_runs_append_instead_of_overwriting_previous_evidence(tmp_path):
    pair(tmp_path)
    pair(tmp_path)
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert len(records) == 4 and len({r["run_id"] for r in records}) == 4
    assert len((tmp_path / "runs.pairs.jsonl").read_text().splitlines()) == 2


def test_unwritable_destination_fails_before_paid_calls(tmp_path):
    from bench.eval.runner import PairRunner

    destination = tmp_path / "runs.jsonl"
    destination.mkdir()
    runtime = FixtureRuntime()
    with pytest.raises(BenchError):
        PairRunner(runtime, destination).pair(question_id="q1", question="What?", corpus="third")
    assert runtime.requests == []


@pytest.mark.parametrize("filename", ["runs.jsonl", "runs.pairs.jsonl"])
def test_interrupted_artifact_tail_rejects_pair_before_paid_calls(tmp_path, filename):
    from bench.eval.runner import PairRunner

    path = tmp_path / filename
    original = b'{"run_id":'
    path.write_bytes(original)
    runtime = FixtureRuntime()
    with pytest.raises(BenchError, match="JSONL"):
        PairRunner(runtime, tmp_path / "runs.jsonl").pair(
            question_id="q1", question="What?", corpus="third"
        )
    assert runtime.requests == []
    assert path.read_bytes() == original


def test_append_rechecks_interrupted_tail_under_lock(tmp_path):
    from bench.eval.runner import PairRunner

    runtime = FixtureRuntime()
    original_ask = runtime.ask
    destination = tmp_path / "runs.jsonl"

    def interrupted_writer(question, corpus, strategy):
        result = original_ask(question, corpus, strategy)
        destination.write_bytes(b'{"run_id":')
        return result

    runtime.ask = interrupted_writer
    with pytest.raises(BenchError, match="JSONL"):
        PairRunner(runtime, destination).pair(question_id="q1", question="What?", corpus="third")
    assert len(runtime.requests) == 1
    assert destination.read_bytes() == b'{"run_id":'
