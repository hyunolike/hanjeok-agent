from __future__ import annotations

import json
import math

import httpx
import pytest

from guide.embeddings import EmbeddingFailure, NvidiaEmbedder, embedder_from_env


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def response(rows):
    return {"data": [{"index": i, "embedding": v} for i, v in enumerate(rows)]}


def vector(first=1.0):
    return [first, *([0.0] * 1023)]


def test_query_and_passages_use_distinct_input_types_and_keep_input_order():
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        assert request.headers["authorization"] == "Bearer test-key"
        rows = response([vector(i + 1) for i in range(len(body["input"]))])
        rows["data"].reverse()
        return httpx.Response(200, json=rows)

    subject = NvidiaEmbedder(api_key="test-key", client=client(handler), batch_size=2)
    assert subject.embed_query("한적한 곳") == vector()
    assert subject.embed(["a", "b", "c"]) == [vector(), vector(), vector()]
    assert [b["input_type"] for b in sent] == ["query", "passage", "passage"]
    assert [b["input"] for b in sent] == [["한적한 곳"], ["a", "b"], ["c"]]
    assert all(b["dimensions"] == 1024 and b["truncate"] == "END" for b in sent)
    assert subject.embed([]) == [] and len(sent) == 3
    assert subject.model_id != "intfloat/multilingual-e5-large"


@pytest.mark.parametrize(
    "rows",
    [
        {"data": []},
        {"data": [{"index": 1, "embedding": vector()}]},
        {"data": [{"index": False, "embedding": vector()}]},
        response([[1.0]]),
        response([[0.0] * 1024]),
        response([[True] * 1024]),
        response([["1"] * 1024]),
        {"data": [{"index": 0, "embedding": vector()}, {"index": 0, "embedding": vector()}]},
    ],
)
def test_malformed_vectors_are_refused(rows):
    subject = NvidiaEmbedder(
        api_key="secret", client=client(lambda _: httpx.Response(200, json=rows))
    )
    with pytest.raises(EmbeddingFailure, match="invalid_response"):
        subject.embed_query("q")


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_values_are_refused(bad):
    body = json.dumps(response([vector(bad)]))
    subject = NvidiaEmbedder(
        api_key="secret", client=client(lambda _: httpx.Response(200, text=body))
    )
    with pytest.raises(EmbeddingFailure, match="invalid_response"):
        subject.embed_query("q")


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_failures_do_not_expose_provider_text_or_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="secret-provider-body")

    subject = NvidiaEmbedder(api_key="secret-key", client=client(handler))
    with pytest.raises(EmbeddingFailure) as caught:
        subject.embed_query("private question")
    assert "secret" not in str(caught.value)
    assert len(calls) == 1


def test_transport_failure_is_sanitized():
    def handler(request):
        raise httpx.ReadTimeout("secret", request=request)

    with pytest.raises(EmbeddingFailure, match="unavailable") as caught:
        NvidiaEmbedder(api_key="secret", client=client(handler)).embed_query("q")
    assert "secret" not in str(caught.value)


def test_missing_key_fails_before_a_request(monkeypatch):
    monkeypatch.setenv("GUIDE_EMBEDDING_PROVIDER", "nvidia")
    with pytest.raises(EmbeddingFailure, match="configuration"):
        embedder_from_env()


def test_provider_typo_never_silently_selects_local(monkeypatch):
    monkeypatch.setenv("GUIDE_EMBEDDING_PROVIDER", "nvdiia")
    with pytest.raises(ValueError, match="GUIDE_EMBEDDING_PROVIDER"):
        embedder_from_env()


def test_local_mode_retains_the_existing_pinned_identity(monkeypatch):
    monkeypatch.delenv("GUIDE_EMBEDDING_PROVIDER", raising=False)
    from bench.embeddings import MODEL, REVISION

    assert embedder_from_env().model_id == f"{MODEL}@{REVISION}"


def test_hosted_model_uses_the_current_non_deprecated_endpoint():
    from guide.embeddings import MODEL

    assert MODEL == "nvidia/nemotron-3.5-embed-1b"


def test_streaming_response_must_finish_within_the_embedding_budget(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("guide.embeddings.time.monotonic", lambda: now[0])

    class Slow(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"data": '
            now[0] = 11.0
            yield json.dumps(response([vector()])["data"]).encode() + b"}"

    subject = NvidiaEmbedder(
        api_key="test", client=client(lambda _: httpx.Response(200, stream=Slow()))
    )
    with pytest.raises(EmbeddingFailure, match="unavailable"):
        subject.embed_query("q")
