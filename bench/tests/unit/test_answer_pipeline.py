import json

import pytest


def make_pipeline(scripted, *replies, passages=None, **options):
    from bench.answer.pipeline import AnswerPipeline
    from bench.graph.query import Passage

    if passages is None:
        passages = [
            Passage(
                "a.md",
                "a.md#0",
                "A is the fact.",
                "A",
                attrs={"alien": {"conflict": "keep this verbatim"}},
            )
        ]
    model = scripted(*replies)
    pipeline = AnswerPipeline(lambda corpus, question: passages, model, **options)
    return pipeline, model


def reply(answer="A is the fact.", citations=None):
    return json.dumps(
        {
            "outcome": "answered",
            "answer": answer,
            "citations": ["a.md"] if citations is None else citations,
        }
    )


def ask(pipeline):
    return pipeline.ask("What is A?", "third-corpus", "revision-1", {"a.md", "b.md"})


def test_prompt_carries_opaque_attrs_and_revision_without_corpus_branches(scripted):
    pipeline, model = make_pipeline(scripted, reply())
    result = ask(pipeline)
    assert result.outcome == "answered"
    assert result.answer == "A is the fact."
    assert result.corpus_revision == "revision-1"
    supplied = json.loads(model.calls[0]["user"])["supplied"]
    assert supplied[0]["attrs"] == {"alien": {"conflict": "keep this verbatim"}}
    assert supplied[0]["text"] == "A is the fact."
    assert model.calls[0]["system"]


def test_invalid_citation_is_repaired_once_and_never_exposed(scripted):
    pipeline, model = make_pipeline(scripted, reply("rejected secret", ["missing.md"]), reply())
    result = ask(pipeline)
    assert result.outcome == "answered"
    assert result.repair_count == 1
    assert len(model.calls) == 2
    assert "rejected secret" not in json.dumps(result.to_dict())
    assert "missing.md" not in model.calls[1]["user"]
    assert json.loads(model.calls[1]["user"])["repair"]


def test_second_invalid_citation_ends_without_a_third_model_call(scripted):
    pipeline, model = make_pipeline(
        scripted, reply("secret one", ["bad.md"]), reply("secret two", ["also-bad.md"])
    )
    result = ask(pipeline)
    assert result.outcome == "invalid_citations"
    assert result.answer is None
    assert result.citations == ()
    assert result.repair_count == 1
    assert len(model.calls) == 2
    assert "secret" not in json.dumps(result.to_dict())


def test_empty_retrieval_declines_without_calling_the_model(scripted):
    pipeline, model = make_pipeline(scripted, passages=[])
    assert ask(pipeline).outcome == "no_grounds"
    assert model.calls == []


def test_model_declines_with_null_answer(scripted):
    pipeline, _ = make_pipeline(scripted, '{"outcome":"no_grounds","answer":null,"citations":[]}')
    result = ask(pipeline)
    assert result.outcome == "no_grounds"
    assert result.answer is None


@pytest.mark.parametrize(
    "raw",
    [
        "garbage",
        "{}",
        '{"outcome":"answered","answer":"x"}',
        '{"outcome":"no_grounds","answer":"leak","citations":[]}',
    ],
)
def test_malformed_output_is_a_named_failure_without_text(scripted, raw):
    pipeline, _ = make_pipeline(scripted, raw)
    result = ask(pipeline)
    assert result.outcome == "model_failed"
    assert result.answer is None


def test_model_exception_is_opaque(scripted):
    pipeline, model = make_pipeline(scripted)

    def broken(*args, **kwargs):
        raise RuntimeError("API secret /private/path")

    model.complete = broken
    result = ask(pipeline)
    assert result.outcome == "model_failed"
    assert "secret" not in repr(result)


def test_call_budget_stops_repair(scripted):
    pipeline, model = make_pipeline(scripted, reply("discard", ["bad.md"]), max_model_calls=1)
    result = ask(pipeline)
    assert result.outcome == "budget_exhausted"
    assert result.answer is None
    assert len(model.calls) == 1


def test_deadline_stops_model_call_after_slow_retrieval(scripted):
    times = iter([0.0, 61.0, 61.0])
    pipeline, model = make_pipeline(scripted, clock=lambda: next(times))
    result = ask(pipeline)
    assert result.outcome == "budget_exhausted"
    assert model.calls == []


def test_each_request_gets_its_own_checkpoint(scripted):
    pipeline, _ = make_pipeline(scripted, reply(), reply())
    first, second = ask(pipeline), ask(pipeline)
    assert first.run_id != second.run_id
    snapshot = pipeline.graph.get_state({"configurable": {"thread_id": first.run_id}})
    assert snapshot.values["outcome"] == "answered"


def test_response_after_deadline_is_discarded_but_usage_is_retained(scripted):
    from bench.answer.pipeline import ModelReply

    now = [0.0]
    pipeline, model = make_pipeline(scripted, clock=lambda: now[0])

    def slow(*args, **kwargs):
        now[0] = 61.0
        return ModelReply(reply("late answer"), 123, 45)

    model.complete = slow
    result = ask(pipeline)
    assert result.outcome == "budget_exhausted"
    assert result.answer is None
    assert (result.prompt_tokens, result.completion_tokens) == (123, 45)
