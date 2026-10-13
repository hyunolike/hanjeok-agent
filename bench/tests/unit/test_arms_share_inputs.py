import json

import pytest

from bench.answer.pipeline import AnswerPipeline, ModelReply
from bench.graph.query import Passage


class RecordingModel:
    def __init__(self):
        self.requests = []

    def complete(self, system, user, **kwargs):
        self.requests.append((system, user))
        return ModelReply('{"outcome":"answered","answer":"fact","citations":["a.md"]}', 20, 5)


def test_both_arms_capture_actual_shared_inputs_with_only_supplied_differing():
    model = RecordingModel()
    passages = [
        Passage("a.md", "a.md#0", "fact", "A", {"arbitrary": ["verbatim"]}),
        Passage("b.md", "b.md#0", "other evidence", "B"),
    ]
    results = [
        AnswerPipeline(lambda c, q, rows=rows: rows, model).ask(
            "What?", "third", "rev", {"a.md", "b.md"}
        )
        for rows in (passages, passages[:1])
    ]
    assert all(r.outcome == "answered" for r in results)
    assert all(r.model_calls == 1 for r in results)
    inputs = [r.inputs for r in results]
    assert [(i["system"], i["user"]) for i in inputs] == model.requests
    assert inputs[0]["system"] == inputs[1]["system"]
    bodies = [json.loads(i["user"]) for i in inputs]
    assert bodies[0].pop("supplied") != bodies[1].pop("supplied")
    assert bodies == [{"question": "What?"}, {"question": "What?"}]
    assert inputs[0]["schema"] == inputs[1]["schema"]
    assert inputs[0]["budget"] == inputs[1]["budget"]
    assert results[0].supplied[0].attrs == {"arbitrary": ["verbatim"]}


@pytest.mark.parametrize("count", [1, 2])
def test_oversize_prompt_is_declared_without_truncating_or_calling_model(count):
    model = RecordingModel()
    rows = [Passage(f"{i}.md", f"{i}.md#0", "거대한 자료" * 1000, "A") for i in range(count)]
    result = AnswerPipeline(lambda c, q: rows, model, max_input_bytes=4000).ask(
        "Question?", "third", "rev", {p.doc for p in rows}
    )
    assert result.outcome == "budget_exhausted"
    assert result.answer is None and result.citations == ()
    assert list(result.supplied) == rows
    assert "input" in result.cause
    assert model.requests == []
    assert result.prompt_tokens == result.completion_tokens == 0
    assert result.model_calls == 0


def test_repair_is_checked_against_the_same_input_limit():
    from bench.answer.pipeline import ModelAnswer
    from bench.answer.prompt import SYSTEM, assemble

    passage = Passage("a.md", "a.md#0", "fact", "A")
    # The first request fits; adding the repair cause makes the second too big.
    initial_bytes = (
        sum(
            len(s.encode())
            for s in (
                SYSTEM,
                assemble("Q?", [passage]),
                json.dumps(ModelAnswer.model_json_schema()),
            )
        )
        + 2048
    )

    class BadCitationModel(RecordingModel):
        def complete(self, system, user, **kwargs):
            self.requests.append((system, user))
            return ModelReply(
                '{"outcome":"answered","answer":"reject me","citations":["missing.md"]}', 12, 6
            )

    model = BadCitationModel()
    result = AnswerPipeline(lambda c, q: [passage], model, max_input_bytes=initial_bytes).ask(
        "Q?", "third", "rev", {"a.md"}
    )
    assert result.outcome == "budget_exhausted" and result.answer is None
    assert len(model.requests) == 1
    assert (result.prompt_tokens, result.completion_tokens) == (12, 6)
    assert result.model_calls == 1


def test_empty_selection_retains_auditable_inputs_without_a_model_call():
    model = RecordingModel()
    result = AnswerPipeline(lambda c, q: [], model).ask("Q?", "third", "rev", set())
    assert result.outcome == "no_grounds"
    assert json.loads(result.inputs["user"]) == {"question": "Q?", "supplied": []}
    assert model.requests == []


def test_failed_provider_attempt_is_distinguished_from_unsubmitted_input():
    class UnavailableModel:
        def complete(self, system, user, **kwargs):
            raise RuntimeError("private failure")

    result = AnswerPipeline(
        lambda c, q: [Passage("a.md", "a#0", "fact", "A")], UnavailableModel()
    ).ask("Q?", "third", "rev", {"a.md"})
    assert result.outcome == "model_failed"
    assert result.model_calls == 1
