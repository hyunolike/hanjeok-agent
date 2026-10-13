"""Lazy RAGAS 0.4 collection metrics, with bounded provider calls and usage."""

import asyncio
import os
from importlib.metadata import version
from threading import RLock

from bench.embeddings import MODEL, REVISION
from bench.provider import BASE_URL, EXTRA_BODY, RequestPacer, api_key, diagnostic, request_pacer
from bench.provider import MODEL as CHAT_MODEL


class RagasJudge:
    def __init__(self, embedder, *, client=None, model=None, min_interval_seconds=None):
        os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
        from openai import AsyncOpenAI
        from ragas.embeddings.base import BaseRagasEmbedding
        from ragas.llms import llm_factory
        from ragas.metrics.collections import (
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
        )

        pacer = (
            request_pacer()
            if client is None and min_interval_seconds is None
            else RequestPacer(2 if min_interval_seconds is None else min_interval_seconds)
        )
        self.errors = []
        self.settings = {
            "name": model or os.environ.get("BENCH_JUDGE_MODEL", CHAT_MODEL),
            "provider": "nvidia",
            "base_url": BASE_URL,
            "enable_thinking": False,
            "temperature": 0,
            "max_tokens": 4096,
            "ragas_version": version("ragas"),
            "answer_relevancy_strictness": 3,
            "response_cache": False,
            "provider_retries": 0,
            "structured_attempts": 1,
            "request_timeout_seconds": 90,
            "minimum_request_interval_seconds": pacer.interval,
            "embedding": {"name": MODEL, "revision": REVISION, "prefix": "query: "},
        }
        self.usage = {
            "model_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "responses_with_usage": 0,
            "calls_without_usage": 0,
        }
        self.client = client or AsyncOpenAI(
            api_key=api_key(), base_url=BASE_URL, max_retries=0, timeout=90
        )
        original = self.client.chat.completions.create

        async def counted(*args, **kwargs):
            await pacer.await_slot()
            self.usage["model_calls"] += 1
            call = self.usage["model_calls"]
            try:
                reply = await original(*args, **kwargs)
            except BaseException as error:
                self.usage["calls_without_usage"] += 1
                self.errors.append({"call": call, **diagnostic(error)})
                raise
            if reply.usage is not None:
                self.usage["responses_with_usage"] += 1
                self.usage["prompt_tokens"] += reply.usage.prompt_tokens
                self.usage["completion_tokens"] += reply.usage.completion_tokens
            else:
                self.usage["calls_without_usage"] += 1
            return reply

        self.client.chat.completions.create = counted
        llm = llm_factory(
            self.settings["name"],
            client=self.client,
            temperature=0,
            max_tokens=4096,
            max_retries=1,
            cache=None,
            extra_body=EXTRA_BODY,
        )
        embedding_lock = RLock()

        class LocalRagasEmbedding(BaseRagasEmbedding):
            def embed_text(self, text, **kwargs):
                with embedding_lock:
                    return embedder.embed_query(text)

            async def aembed_text(self, text, **kwargs):
                return await asyncio.to_thread(self.embed_text, text)

        embedding = LocalRagasEmbedding()
        self.metrics = {
            "faithfulness": Faithfulness(llm=llm),
            "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embedding, strictness=3),
            "context_precision": ContextPrecision(llm=llm),
            "context_recall": ContextRecall(llm=llm),
        }

    async def score(self, metric, **kwargs):
        return (await self.metrics[metric].ascore(**kwargs)).value

    async def close(self):
        await self.client.close()
