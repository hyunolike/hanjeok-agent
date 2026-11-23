"""Bound execution, including work still finishing after an SSE disconnect."""

from __future__ import annotations

import asyncio
from threading import Lock

import anyio
from starlette.responses import StreamingResponse


async def complete_in_thread(function, *args):
    """Do not abandon synchronous work even under direct asyncio cancellation."""
    operation = asyncio.create_task(anyio.to_thread.run_sync(function, *args))
    try:
        return await asyncio.shield(operation)
    except asyncio.CancelledError:
        with anyio.CancelScope(shield=True):
            while not operation.done():
                try:
                    await asyncio.shield(operation)
                except asyncio.CancelledError:
                    continue
            # Consume an exception without replacing the caller's cancellation.
            if not operation.cancelled():
                operation.exception()
        raise


class Lease:
    def __init__(self, owner, visit, on_release):
        self.owner, self.visit, self.on_release = owner, visit, on_release
        self.released = False

    def release(self):
        with self.owner.lock:
            if self.released:
                return
            self.released = True
            self.owner.active.remove(self.visit)
        if self.on_release is not None:
            self.on_release()


class Admission:
    def __init__(self, capacity: int):
        if not 1 <= capacity <= 8:
            raise ValueError("GUIDE_MAX_CONCURRENT must be 1 to 8")
        self.capacity, self.active, self.lock = capacity, set(), Lock()

    def acquire(self, visit: str, *, on_release=None) -> Lease | None:
        with self.lock:
            if visit in self.active or len(self.active) >= self.capacity:
                return None
            self.active.add(visit)
            return Lease(self, visit, on_release)


def _next(iterator):
    try:
        return True, next(iterator)
    except StopIteration:
        return False, None


class ManagedStream(StreamingResponse):
    def __init__(self, content, lease: Lease, **kwargs):
        self.iterator, self.lease = iter(content), lease
        super().__init__(self.iterate(), **kwargs)

    async def iterate(self):
        try:
            while True:
                # Cancellation must wait for a running synchronous lookup/model
                # call. Otherwise a disconnected visitor could bypass admission.
                present, item = await complete_in_thread(_next, self.iterator)
                if not present:
                    break
                yield item
        finally:
            await self.finish()

    async def finish(self):
        if self.lease.released:
            return
        with anyio.CancelScope(shield=True):
            try:
                close = getattr(self.iterator, "close", None)
                if close is not None:
                    await complete_in_thread(close)
            finally:
                self.lease.release()

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await self.body_iterator.aclose()
                finally:
                    await self.finish()
