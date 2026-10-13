"""Fakes that keep the default suite offline.

The constitution puts paid evaluation outside CI and requires unit tests to pass
with no network and no API key. The two places that would otherwise reach out
are embedding and the chat model, so both have deterministic stand-ins here.
"""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Sequence

import pytest

from bench.graph.store import EMBEDDING_DIM


class FakeEmbedder:
    """Deterministic, offline, and roughly direction-preserving.

    Hashing alone would make every pair of texts equidistant, which would let a
    retrieval test pass while retrieval was broken. Instead each token
    contributes to a fixed set of dimensions, so texts sharing vocabulary end up
    closer than texts that share none — enough structure for a nearest-neighbour
    assertion to mean something, with no model and no download.
    """

    dim = EMBEDDING_DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._one(text)

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for k in range(4):
                idx = int.from_bytes(digest[k * 4 : k * 4 + 4], "big") % self.dim
                vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            # An empty or whitespace-only chunk. A zero vector has no direction
            # and cosine similarity against it is undefined, so give it a fixed
            # position instead of letting the index decide.
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]


class ScriptedChatModel:
    """Returns prepared replies in order and records what it was asked.

    `calls` is what the Principle II test reads: it compares the prompts the two
    strategies produced, and the only permitted difference is supplied passages.
    """

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, **kwargs) -> str:
        self.calls.append({"system": system, "user": user, **kwargs})
        if not self._replies:
            raise AssertionError("ScriptedChatModel ran out of prepared replies")
        return self._replies.pop(0)


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def scripted():
    def make(*replies: str) -> ScriptedChatModel:
        return ScriptedChatModel(replies)

    return make


@pytest.fixture(autouse=True)
def no_real_api_key(monkeypatch: pytest.MonkeyPatch):
    """Remove provider keys for the duration of every unit test.

    Without this, a developer with a key exported would not notice that a code
    path reaches a paid API — it would simply work for them and fail in CI, or
    worse, work everywhere and quietly bill. Integration and costly tests opt
    back in by being deselected from the default run, not by reading a key here.
    """
    for name in list(os.environ):
        if name.endswith("_API_KEY"):
            monkeypatch.delenv(name, raising=False)
