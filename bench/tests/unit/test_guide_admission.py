from __future__ import annotations

import asyncio
from threading import Event

import pytest

from guide.admission import Admission, ManagedStream
from guide.visits import VisitCapacity, Visits


def test_global_and_same_visit_limits_release_idempotently():
    admission = Admission(2)
    first = admission.acquire("a")
    assert first is not None
    assert admission.acquire("a") is None
    second = admission.acquire("b")
    assert second is not None and admission.acquire("c") is None
    first.release()
    first.release()
    assert admission.acquire("c") is not None


@pytest.mark.asyncio
async def test_disconnect_keeps_slot_until_the_blocked_sync_operation_exits():
    admission = Admission(1)
    lease = admission.acquire("visit")
    entered, unblock, closed = Event(), Event(), Event()

    def content():
        try:
            yield "first"
            entered.set()
            unblock.wait(timeout=5)
            yield "second"
        finally:
            closed.set()

    response = ManagedStream(content(), lease)
    disconnected = asyncio.Event()

    async def receive():
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        pass

    task = asyncio.create_task(
        response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send)
    )
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        disconnected.set()
        await asyncio.sleep(0.05)
        assert admission.acquire("visit") is None
        assert not closed.is_set()
    finally:
        unblock.set()
        await asyncio.wait_for(task, 3)
    assert closed.is_set()
    assert admission.acquire("visit") is not None


@pytest.mark.asyncio
async def test_iterator_exception_still_closes_and_releases():
    admission = Admission(1)

    def content():
        yield "first"
        raise RuntimeError("failed")

    response = ManagedStream(content(), admission.acquire("a"))

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        pass

    with pytest.raises(RuntimeError, match="failed"):
        await response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send)
    assert admission.acquire("a") is not None


@pytest.mark.asyncio
async def test_direct_task_cancellation_keeps_slot_until_sync_operation_finishes():
    admission = Admission(1)
    entered, unblock, closed = Event(), Event(), Event()

    def content():
        try:
            entered.set()
            unblock.wait(timeout=5)
            yield "done"
        finally:
            closed.set()

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        pass

    response = ManagedStream(content(), admission.acquire("a"))
    task = asyncio.create_task(
        response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    )
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0.05)
        assert admission.acquire("a") is None
        assert not closed.is_set()
    finally:
        unblock.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert closed.is_set() and admission.acquire("a") is not None


@pytest.mark.asyncio
async def test_direct_cancellation_waits_for_pre_stream_readiness_work():
    from guide.admission import complete_in_thread

    admission = Admission(1)
    lease = admission.acquire("a")
    entered, unblock, finished = Event(), Event(), Event()

    def readiness():
        entered.set()
        unblock.wait(timeout=5)
        finished.set()

    async def request():
        try:
            await complete_in_thread(readiness)
        finally:
            lease.release()

    task = asyncio.create_task(request())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0.05)
        assert admission.acquire("a") is None and not finished.is_set()
    finally:
        unblock.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert finished.is_set() and admission.acquire("a") is not None


@pytest.mark.asyncio
async def test_slot_is_free_before_http_eof_is_sent_after_work_finishes():
    admission = Admission(1)
    at_eof, allow_eof = asyncio.Event(), asyncio.Event()
    response = ManagedStream(iter(["complete"]), admission.acquire("a"))

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            at_eof.set()
            await allow_eof.wait()

    task = asyncio.create_task(response(
        {"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send
    ))
    try:
        await asyncio.wait_for(at_eof.wait(), 2)
        assert admission.acquire("a") is not None
    finally:
        allow_eof.set()
        await task


def test_visit_cap_preserves_active_threads_and_expiry_frees_capacity():
    now, expired = [0.0], []
    visits = Visits(max_visits=1, clock=lambda: now[0], on_expire=expired.append)
    visit = visits.open(None)
    visits.pin(visit)
    now[0] = 1801
    with pytest.raises(VisitCapacity):
        visits.open(None)
    assert expired == []
    visits.unpin(visit)
    now[0] += 1801
    assert visits.open(None) != visit
    assert expired == [visit]


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_capacities_are_configuration_errors(limit):
    with pytest.raises(ValueError):
        Visits(max_visits=limit)
    with pytest.raises(ValueError):
        Admission(limit)
