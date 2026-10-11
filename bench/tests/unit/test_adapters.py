import json

import httpx
import pytest


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
