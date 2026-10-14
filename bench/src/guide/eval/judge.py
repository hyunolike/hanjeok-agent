"""The bench's RAGAS judge, given a transport that waits out rate limits.

The bench's judge never retries: a retried call would blur what one measured
call costs. With the hosted key shared across projects, the guide's first
judged run got an answer to 1 of 72 judge requests — the rest were 429s within
two minutes. A judge that mostly cannot be heard measures the provider's quota,
not the answers, so here a 429 is waited out and tried again.

Nothing about what is judged changes: same metrics, same model, same settings.
The retries are below RAGAS, at the HTTP layer, so one metric's several calls
each get their own patience.
"""

from __future__ import annotations

import asyncio

import httpx

WAITS_S = (15.0, 30.0, 60.0, 120.0)


class PatientTransport(httpx.AsyncBaseTransport):
    def __init__(
        self, inner: httpx.AsyncBaseTransport, *, waits=WAITS_S, sleep=asyncio.sleep
    ) -> None:
        self._inner, self._waits, self._sleep = inner, tuple(waits), sleep
        self.waited = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for wait in (*self._waits, None):
            response = await self._inner.handle_async_request(request)
            if response.status_code != 429 or wait is None:
                return response
            await response.aclose()
            self.waited += 1
            await self._sleep(wait)
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._inner.aclose()


def patient_judge(embedder):
    """A `RagasJudge` whose requests wait out 429s. Returns the judge and the
    transport, whose `waited` says how often that happened."""
    from openai import AsyncOpenAI

    from bench.eval.judge import RagasJudge
    from bench.provider import BASE_URL, api_key

    transport = PatientTransport(httpx.AsyncHTTPTransport())
    client = AsyncOpenAI(
        api_key=api_key(),
        base_url=BASE_URL,
        max_retries=0,
        # One request may now include up to 225 s of waiting before it is sent again.
        timeout=httpx.Timeout(90.0),
        http_client=httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(90.0)),
    )
    judge = RagasJudge(embedder, client=client, min_interval_seconds=3)
    judge.settings["provider_retries"] = f"429 only, waits {list(WAITS_S)} s"
    return judge, transport
