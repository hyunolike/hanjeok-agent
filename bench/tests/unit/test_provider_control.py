import json
from dataclasses import replace

import httpx
import pytest


def test_pacer_reserves_start_slots_across_sync_and_async_consumers():
    from bench.provider import RequestPacer

    now = [10.0]
    sleeps = []

    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    pacer = RequestPacer(3, clock=lambda: now[0], sleep=sleep)
    pacer.wait()
    pacer.wait()
    assert sleeps == [3.0]
    assert pacer.reserve() == 3.0
    now[0] += 8
    assert pacer.reserve() == 0


def test_status_failures_are_stored_without_provider_body_headers_or_retries(tmp_path):
    from langchain_openai import ChatOpenAI

    from bench.answer.pipeline import AnswerPipeline
    from bench.eval.runner import PairRunner
    from bench.graph.query import Passage
    from bench.models import AnswerModel

    calls = []

    def unavailable(request):
        calls.append(request)
        return httpx.Response(
            429,
            json={"error": {"message": "secret-body nvapi-should-never-be-stored"}},
            headers={"retry-after": "secret-header"},
        )

    model = AnswerModel(
        chat=ChatOpenAI(
            model="test",
            api_key="fake",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(unavailable)),
        )
    )

    class Runtime:
        model_settings = model.settings

        def ask(self, question, corpus, strategy):
            result = AnswerPipeline(lambda c, q: [Passage("a.md", "a#0", "fact", "A")], model).ask(
                question, corpus, "rev", {"a.md"}
            )
            return replace(result, corpus_size=1, corpus_generation="g")

    pair = PairRunner(Runtime(), tmp_path / "arms.jsonl").pair(
        question_id="q", question="Q?", corpus="test"
    )
    assert len(calls) == 2
    for arm in (pair.whole, pair.graph):
        assert arm.outcome == "model_failed" and arm.model_calls == 1
        assert getattr(arm, "provider_errors", []) == [{"kind": "rate_limit", "http_status": 429}]
        assert arm.answer is None
    artifact = (tmp_path / "arms.jsonl").read_text()
    assert "secret-body" not in artifact and "secret-header" not in artifact
    assert "nvapi-" not in artifact
    assert json.loads(artifact.splitlines()[0])["provider_errors"][0]["http_status"] == 429


@pytest.mark.parametrize("interval", [-1, float("nan"), float("inf")])
def test_invalid_provider_pacing_is_rejected(interval):
    from bench.provider import RequestPacer

    with pytest.raises(ValueError):
        RequestPacer(interval)


def test_pacing_cannot_start_a_provider_call_after_the_answer_deadline():
    from langchain_openai import ChatOpenAI

    from bench.answer.pipeline import AnswerPipeline
    from bench.graph.query import Passage
    from bench.models import AnswerModel
    from bench.provider import RequestPacer

    calls = []
    sleeps = []
    chat = ChatOpenAI(
        model="test",
        api_key="fake",
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(503))
        ),
    )
    model = AnswerModel(chat=chat)
    model.pacer = RequestPacer(3, clock=lambda: 10.0, sleep=sleeps.append)
    model.pacer.reserve()  # next slot is three seconds away, answer has one second
    result = AnswerPipeline(
        lambda c, q: [Passage("a.md", "a#0", "fact", "A")],
        model,
        deadline_ms=1000,
    ).ask("Q?", "test", "rev", {"a.md"})
    assert calls == [] and sleeps == []
    assert result.outcome == "budget_exhausted" and result.model_calls == 0
