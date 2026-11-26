"""Embedding selection shared by serving, loading and evaluation.

The external adapter never imports a local model. Its identity also covers
preprocessing: equal vector widths do not make different models compatible.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Sequence

import httpx

from bench.graph.store import EMBEDDING_DIM
from bench.provider import PacingDeadline, api_key, request_pacer

MODEL = "nvidia/nemotron-3.5-embed-1b"
URL = "https://integrate.api.nvidia.com/v1/embeddings"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class EmbeddingFailure(Exception):
    """A category only: no provider body, input text, URL or credentials."""


class NvidiaEmbedder:
    requires_identity = True

    def __init__(self, *, api_key: str, client=None, batch_size: int = 16) -> None:
        if not api_key or not 1 <= batch_size <= 16:
            raise EmbeddingFailure("configuration")
        self.model_id = f"{MODEL}@1024:input-type-v1:truncate-END:l2"
        self.settings = {
            "name": MODEL,
            "model_id": self.model_id,
            "dimensions": 1024,
            "input_type": "query",
            "truncate": "END",
            "normalize": "l2",
        }
        self._key, self._batch_size = api_key, batch_size
        self._owned = client is None
        self._client = client or httpx.Client(
            timeout=10, limits=httpx.Limits(max_connections=2, max_keepalive_connections=2)
        )
        self._pacer = request_pacer() if self._owned else None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        rows = []
        for start in range(0, len(texts), self._batch_size):
            rows.extend(self._request(list(texts[start : start + self._batch_size]), "passage"))
        return rows

    def embed_query(self, text: str) -> list[float]:
        return self._request([text], "query")[0]

    def _request(self, texts: list[str], kind: str) -> list[list[float]]:
        started = time.monotonic()
        try:
            if self._pacer is not None:
                self._pacer.wait(timeout=10)
            left = 10 - (time.monotonic() - started)
            if left <= 0:
                raise EmbeddingFailure("unavailable")
            with self._client.stream(
                "POST",
                URL,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": MODEL,
                    "input": texts,
                    "input_type": kind,
                    "dimensions": EMBEDDING_DIM,
                    "encoding_format": "float",
                    "truncate": "END",
                },
                timeout=left,
            ) as response:
                if response.status_code != 200:
                    raise EmbeddingFailure("unavailable")
                body = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() - started >= 10:
                        raise EmbeddingFailure("unavailable")
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise EmbeddingFailure("invalid_response")
                payload = json.loads(body)
            if time.monotonic() - started >= 10:
                raise EmbeddingFailure("unavailable")
            data = payload["data"]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError
            vectors = [None] * len(texts)
            for row in data:
                index, vector = row["index"], row["embedding"]
                if (
                    type(index) is not int
                    or not 0 <= index < len(texts)
                    or vectors[index] is not None
                ):
                    raise ValueError
                if (
                    not isinstance(vector, list)
                    or len(vector) != EMBEDDING_DIM
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector)
                ):
                    raise ValueError
                norm = math.hypot(*vector)
                if not math.isfinite(norm) or norm == 0:
                    raise ValueError
                vectors[index] = [v / norm for v in vector]
            return vectors
        except (httpx.HTTPError, PacingDeadline):
            raise EmbeddingFailure("unavailable") from None
        except (ValueError, KeyError, TypeError, OverflowError):
            raise EmbeddingFailure("invalid_response") from None

    def close(self) -> None:
        if self._owned:
            self._client.close()


def compatible(embedder, *identities: str | None) -> bool:
    """Only legacy local graphs may omit the stamp. Never mix named models."""
    expected = getattr(embedder, "model_id", None)
    strict = getattr(embedder, "requires_identity", False)
    return all(value == expected or (value is None and not strict) for value in identities)


def embedder_from_env():
    provider = os.environ.get("GUIDE_EMBEDDING_PROVIDER", "local")
    if provider == "local":
        from bench.embeddings import LocalEmbedder

        return LocalEmbedder()
    if provider != "nvidia":
        raise ValueError("GUIDE_EMBEDDING_PROVIDER must be local or nvidia")
    try:
        key = api_key()
    except ValueError:
        raise EmbeddingFailure("configuration") from None
    return NvidiaEmbedder(api_key=key)
