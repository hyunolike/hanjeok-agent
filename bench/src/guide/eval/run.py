"""Ask every question of a set under each strategy, from one set of facts.

The two strategies must differ in one thing: whether relatedness links may be
followed. Everything else is held the same here, in code, rather than hoped
for — the same questions on the same day, the same model object, the same
instructions, and **the same Hanjeok responses**. Congestion forecasts change
daily and even between two calls, so each response is fetched once and both
strategies read that one copy (constitution, Principle II).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import date
from uuid import uuid4

from guide.agent import Agent
from guide.eval.questions import Question
from guide.forbidden import check, evidence_from
from guide.live import LiveClient, LiveError
from guide.model import ModelFailure

STRATEGIES = ("vector", "graph")
# An evaluation has nobody waiting, so it can outlast a rate limit that a
# visitor's question cannot. Seconds, in order.
PATIENT_WAITS_S = (15.0, 30.0, 60.0, 120.0)


class PatientModel:
    """Waits out the provider's rate limit without charging the question for it.

    A question has sixty seconds. If a throttled provider ate that budget, the
    report would measure the provider's quota that afternoon, not the agent:
    the first real run lost ten of twenty-four runs that way. So the wait
    happens here and `clock` runs slow by exactly the time waited. How often it
    happened is counted and published with the report.
    """

    def __init__(
        self, inner, *, waits=PATIENT_WAITS_S, sleep=time.sleep, clock=time.monotonic
    ) -> None:
        self._inner, self._waits, self._sleep, self._clock = inner, tuple(waits), sleep, clock
        self.paused = 0.0
        self.waits = 0

    @property
    def settings(self) -> dict:
        return self._inner.settings

    @property
    def usage(self) -> dict:
        return getattr(self._inner, "usage", {})

    def clock(self) -> float:
        return self._clock() - self.paused

    def decide(self, system, user, schema, *, timeout):
        for wait in (*self._waits, None):
            try:
                return self._inner.decide(system, user, schema, timeout=timeout)
            except ModelFailure as failure:
                if failure.kind != "rate_limit" or wait is None:
                    raise
                started = self._clock()
                self._sleep(wait)
                self.paused += max(wait, self._clock() - started)
                self.waits += 1
        raise AssertionError("unreachable")


class SharedLive:
    """One Hanjeok response per (endpoint, place, date), for every strategy.

    A failure is shared too. If the first strategy could not reach Hanjeok for
    a place, the second is told the same, rather than getting a second chance
    the first did not have.
    """

    def __init__(self, inner: LiveClient) -> None:
        self._inner = inner
        self._seen: dict[tuple, object] = {}
        self.mode = inner.mode
        self.recording = inner.recording

    def today(self) -> date:
        return self._inner.today()

    def _once(self, kind: str, place_id: int, day: str):
        key = (kind, place_id, day)
        if key not in self._seen:
            try:
                self._seen[key] = getattr(self._inner, kind)(place_id, day)
            except LiveError as error:
                self._seen[key] = error
        found = self._seen[key]
        if isinstance(found, LiveError):
            raise found
        return found

    def congestion(self, place_id: int, day: str):
        return self._once("congestion", place_id, day)

    def alternatives(self, place_id: int, day: str):
        return self._once("alternatives", place_id, day)

    def fetched_at(self) -> str | None:
        """The earliest time any response in this run was fetched."""
        times = [r.fetched_at for r in self._seen.values() if not isinstance(r, LiveError)]
        return min(times) if times else None


def run_one(question: Question, strategy: str, *, model, places, policy, live, today: date) -> dict:
    """One question under one strategy, as a run record."""
    clock = model.clock if isinstance(model, PatientModel) else time.monotonic
    waited = getattr(model, "waits", 0)
    agent = Agent(model, places, policy, live, strategy=strategy, clock=clock)
    before = dict(getattr(model, "usage", {}))
    result = agent.ask(question.question, lambda name, data: None, today=today)
    after = getattr(model, "usage", {})
    fetched = agent._lookups.fetched
    return {
        "run_id": str(uuid4()),
        "question_id": question.id,
        "kind": question.kind,
        "strategy": strategy,
        "question": question.question,
        "expect": question.expect,
        "needs": list(question.needs),
        "outcome": result.outcome,
        "cause": result.cause,
        "answer": result.answer,
        "citations": list(result.citations),
        "partial": result.partial,
        "steps": result.steps,
        "fetched": list(result.fetched),
        "passages": [asdict(passage) for passage in fetched.passages],
        "forbidden": check(result.answer, evidence_from(result, places.gazetteer(), fetched)),
        "model_calls": result.model_calls,
        "prompt_tokens": after.get("prompt_tokens", 0) - before.get("prompt_tokens", 0),
        "completion_tokens": after.get("completion_tokens", 0) - before.get("completion_tokens", 0),
        "elapsed_ms": result.elapsed_ms,
        "model_failure": result.model_failure,
        "rejections": result.rejections,
        "rate_limit_waits": getattr(model, "waits", 0) - waited,
        # Kept so "the two arms saw the same thing" can be checked afterwards
        # from the record, not only asserted in a test.
        "prompts": result.prompts,
    }


def run(
    questions: Sequence[Question],
    *,
    model,
    places,
    policy,
    live: LiveClient,
    today: date,
    strategies: Sequence[str] = STRATEGIES,
    on_run: Callable[[dict], None] | None = None,
) -> tuple[list[dict], SharedLive]:
    shared = SharedLive(live)
    records: list[dict] = []
    for question in questions:
        # Strategy by strategy within a question, not question by question
        # within a strategy: whatever drifts over a long run drifts for both.
        for strategy in strategies:
            record = run_one(
                question,
                strategy,
                model=model,
                places=places,
                policy=policy,
                live=shared,
                today=today,
            )
            records.append(record)
            if on_run is not None:
                on_run(record)
    return records, shared
