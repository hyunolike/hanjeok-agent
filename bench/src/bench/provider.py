"""The benchmark's sole hosted provider: NVIDIA NIM, without paid fallbacks."""

import asyncio
import math
import os
import time
from threading import Lock

BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}


class RequestPacer:
    """Reserve request-start slots shared by synchronous and asynchronous calls."""

    def __init__(self, interval, *, clock=time.monotonic, sleep=time.sleep):
        if not math.isfinite(interval) or interval < 0:
            raise ValueError("invalid provider request interval")
        self.interval, self.clock, self.sleep = interval, clock, sleep
        self._next = 0.0
        self._lock = Lock()

    def reserve(self, *, timeout=None):
        with self._lock:
            now = self.clock()
            start = max(now, self._next)
            if timeout is not None and start - now >= timeout:
                raise PacingDeadline("provider pacing exceeds remaining answer budget")
            self._next = start + self.interval
            return start - now

    def wait(self, *, timeout=None):
        if delay := self.reserve(timeout=timeout):
            self.sleep(delay)

    async def await_slot(self):
        if delay := self.reserve():
            await asyncio.sleep(delay)


_pacer = None
_pacer_lock = Lock()


def request_pacer():
    global _pacer
    with _pacer_lock:
        if _pacer is None:
            _pacer = RequestPacer(float(os.environ.get("BENCH_REQUEST_INTERVAL_SECONDS", "3")))
        return _pacer


def diagnostic(error):
    """Keep a small allowlist; never persist error text, response bodies or headers."""
    from openai import APIConnectionError, APITimeoutError

    if isinstance(error, ProviderFailure):
        return dict(error.diagnostic)
    status = getattr(error, "status_code", None)
    status = status if type(status) is int and 100 <= status <= 599 else None
    kind = "provider_error"
    if status == 429:
        kind = "rate_limit"
    elif status in (401, 403):
        kind = "authentication"
    elif status is not None and status >= 500:
        kind = "provider_unavailable"
    elif isinstance(error, APITimeoutError):
        kind = "timeout"
    elif isinstance(error, APIConnectionError):
        kind = "connection"
    return {"kind": kind, "http_status": status}


class ProviderFailure(Exception):
    def __init__(self, error):
        self.diagnostic = diagnostic(error)
        super().__init__(self.diagnostic["kind"])


class PacingDeadline(TimeoutError):
    """No provider call was started; the local answer budget ran out waiting."""


def api_key():
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        raise ValueError("NVIDIA_API_KEY is required")
    return key
