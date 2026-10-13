import json

import httpx
import pytest


def test_lazy_model_pins_settings_before_pair_execution(monkeypatch):
    from bench.models import LazyAnswerModel

    monkeypatch.setenv("BENCH_ANSWER_MODEL", "original-model")
    model = LazyAnswerModel()
    monkeypatch.setenv("BENCH_ANSWER_MODEL", "changed-model")
    assert model.settings["name"] == "original-model"
    assert model.settings["temperature"] == 0
    settings = model.settings
    settings["name"] = "mutation"
    assert model.settings["name"] == "original-model"


def test_local_embedder_prefixes_queries_and_passages_without_loading_a_model():
    from bench.embeddings import LocalEmbedder

    class Encoder:
        def encode(self, texts, **kwargs):
            self.texts, self.options = texts, kwargs
            return [[1.0] + [0.0] * 1023 for _ in texts]

    encoder = Encoder()
    embedder = LocalEmbedder(encoder=encoder)
    embedder.embed(["문서"])
    assert encoder.texts == ["passage: 문서"]
    assert encoder.options["normalize_embeddings"] is True
    embedder.embed_query("질문")
    assert encoder.texts == ["query: 질문"]


def test_chat_adapter_uses_real_transport_shape_and_counts_billed_usage():
    from langchain_openai import ChatOpenAI

    from bench.models import AnswerModel

    bodies = []

    def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "test-id",
                "object": "chat.completion",
                "model": "gpt-4o",
                "created": 0,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"outcome":"answered","answer":"fact",'
                            '"citations":["a.md"]}',
                            "refusal": None,
                        },
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
            },
        )

    chat = ChatOpenAI(
        model="gpt-4o",
        api_key="fake-for-test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    reply = AnswerModel(chat=chat).complete("unchanged system", "user data", timeout=1)
    assert json.loads(reply.text)["answer"] == "fact"
    assert (reply.prompt_tokens, reply.completion_tokens) == (123, 45)
    assert bodies[0]["messages"] == [
        {"role": "system", "content": "unchanged system"},
        {"role": "user", "content": "user data"},
    ]
    assert bodies[0]["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize("refusal", [False, True])
def test_malformed_and_refused_completions_retain_actual_billed_usage(refusal):
    from langchain_openai import ChatOpenAI

    from bench.answer.pipeline import AnswerPipeline
    from bench.graph.query import Passage
    from bench.models import AnswerModel

    def respond(request):
        return httpx.Response(
            200,
            json={
                "id": "test-id",
                "object": "chat.completion",
                "model": "gpt-4o",
                "created": 0,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": None if refusal else "malformed content",
                            "refusal": "private refusal message" if refusal else None,
                        },
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
            },
        )

    chat = ChatOpenAI(
        model="gpt-4o",
        api_key="fake",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    pipeline = AnswerPipeline(
        lambda c, q: [Passage("a.md", "a#0", "fact", "A")], AnswerModel(chat=chat)
    )
    result = pipeline.ask("question", "synthetic", "r", {"a.md"})
    assert result.outcome == "model_failed"
    assert (result.prompt_tokens, result.completion_tokens) == (123, 45)
    assert result.cause == (
        "answering model refused" if refusal else "answering model returned malformed output"
    )
    assert result.answer is None
    assert "private refusal" not in repr(result)


def test_output_limit_exception_retains_available_usage_in_failure_record(tmp_path):
    from dataclasses import replace

    from langchain_openai import ChatOpenAI

    from bench.answer.pipeline import AnswerPipeline
    from bench.eval.runner import PairRunner
    from bench.graph.query import Passage
    from bench.models import AnswerModel

    def respond(request):
        return httpx.Response(
            200,
            json={
                "id": "limited",
                "object": "chat.completion",
                "model": "gpt-4o",
                "created": 0,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length",
                        "message": {
                            "role": "assistant",
                            "content": '{"outcome":"answered","answer":"discard partial',
                            "refusal": None,
                        },
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 800, "total_tokens": 923},
            },
        )

    chat = ChatOpenAI(
        model="gpt-4o",
        api_key="fake",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    model = AnswerModel(chat=chat)

    class Runtime:
        model_settings = model.settings

        def ask(self, question, corpus, strategy):
            result = AnswerPipeline(lambda c, q: [Passage("a.md", "a#0", "fact", "A")], model).ask(
                question, corpus, "rev", {"a.md"}
            )
            return replace(result, corpus_size=1, corpus_generation="generation")

    result = PairRunner(Runtime(), tmp_path / "runs.jsonl").pair(
        question_id="limited", question="Q?", corpus="third"
    )
    assert not result.scoring_runs
    for record in (result.whole, result.graph):
        assert record.outcome == "budget_exhausted"
        assert (record.prompt_tokens, record.completion_tokens, record.model_calls) == (123, 800, 1)
        assert record.answer is None and record.cited_paths == []
    assert "discard partial" not in (tmp_path / "runs.jsonl").read_text()


def test_default_answer_uses_only_nvidia_endpoint_and_key(monkeypatch):
    from langchain_openai import ChatOpenAI

    from bench.models import AnswerModel

    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-fake")
    monkeypatch.setenv("OPENAI_API_KEY", "never-use-this")
    bodies = []

    def respond(request):
        assert str(request.url) == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer nvidia-fake"
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "nvidia",
                "object": "chat.completion",
                "created": 0,
                "model": "nvidia/nemotron-3-super-120b-a12b",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"outcome":"answered","answer":"fact",'
                            '"citations":["a.md"]}',
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    def configured(**kwargs):
        return ChatOpenAI(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )

    monkeypatch.setattr("bench.models.ChatOpenAI", configured)
    model = AnswerModel()
    reply = model.complete("system", "user")
    assert json.loads(reply.text)["answer"] == "fact"
    assert model.settings["provider"] == "nvidia"
    assert bodies[0]["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert bodies[0]["chat_template_kwargs"]["enable_thinking"] is False
    assert "nvidia-fake" not in json.dumps(model.settings)


def test_openai_key_cannot_substitute_for_missing_nvidia_key(monkeypatch):
    from bench.models import AnswerModel

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-fallback")
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        AnswerModel()
