import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI


def test_ragas_uses_nvidia_json_transport_and_preserves_provider_usage():
    from bench.eval.judge import RagasJudge

    replies = [
        {"statements": ["Alpha is true."]},
        {
            "statements": [
                {
                    "statement": "Alpha is true.",
                    "reason": "Explicit in supplied evidence.",
                    "verdict": 1,
                }
            ]
        },
    ]
    requests = []

    def respond(request):
        assert request.url.host == "integrate.api.nvidia.com"
        body = json.loads(request.content)
        requests.append(body)
        assert body["chat_template_kwargs"]["enable_thinking"] is False
        assert body["response_format"]["type"] == "json_object"
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
                        "message": {"role": "assistant", "content": json.dumps(replies.pop(0))},
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            },
        )

    client = AsyncOpenAI(
        api_key="fake",
        base_url="https://integrate.api.nvidia.com/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    judge = RagasJudge(None, client=client, min_interval_seconds=0)

    async def evaluate():
        try:
            return await judge.score(
                "faithfulness",
                user_input="What is Alpha?",
                response="Alpha is true.",
                retrieved_contexts=["Alpha is true."],
            )
        finally:
            await judge.close()

    assert asyncio.run(evaluate()) == 1
    assert len(requests) == 2
    assert judge.usage == {
        "model_calls": 2,
        "prompt_tokens": 24,
        "completion_tokens": 12,
        "responses_with_usage": 2,
        "calls_without_usage": 0,
    }
    assert judge.settings["provider"] == "nvidia"
    assert judge.settings["response_cache"] is False


def test_judge_never_uses_openai_key_as_fallback(monkeypatch):
    from bench.eval.judge import RagasJudge

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-nvidia-credential")
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        RagasJudge(None)


def test_quota_failure_has_one_attempt_and_unknown_usage():
    from instructor.core.exceptions import InstructorRetryException

    from bench.eval.judge import RagasJudge

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "private provider detail",
                    "type": "rate_limit",
                    "code": "rate_limit",
                }
            },
        )

    client = AsyncOpenAI(
        api_key="fake",
        base_url="https://integrate.api.nvidia.com/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    judge = RagasJudge(None, client=client, min_interval_seconds=0)

    async def evaluate():
        try:
            with pytest.raises(InstructorRetryException):
                await judge.score(
                    "faithfulness", user_input="What?", response="fact", retrieved_contexts=["fact"]
                )
        finally:
            await judge.close()

    asyncio.run(evaluate())
    assert len(calls) == judge.usage["model_calls"] == 1
    assert judge.usage["calls_without_usage"] == 1
    assert judge.usage["responses_with_usage"] == 0
    assert "private provider" not in json.dumps(judge.usage)
    assert judge.errors == [{"call": 1, "kind": "rate_limit", "http_status": 429}]
    assert "private provider" not in json.dumps(judge.errors)
