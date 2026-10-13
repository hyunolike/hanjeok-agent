"""Who is asking, what they asked before, and how much they may ask.

All in memory. A visit is a browser tab's conversation; it expires thirty
minutes after its last question and is gone on restart. That is deliberate:
this demo keeps no record of visitors, so there is nothing to protect, export
or delete (spec, Out of Scope).

The limits exist because every question spends hosted model quota and calls
Hanjeok, which has no rate limiting of its own (spec FR-030).
"""

from __future__ import annotations

import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from guide.scope import Turn

VISIT_TTL_S = 30 * 60
WINDOW_S = 60 * 60
DAY_S = 24 * 60 * 60
MAX_TURNS = 10
# A visit id is a bearer token for nothing but a conversation's context, but it
# is still unguessable: one visitor must not be able to read another's turns.
_ID_BYTES = 16


@dataclass(frozen=True, slots=True)
class Limit:
    scope: str
    """`visitor` or `day`."""

    retry_after_s: int


@dataclass(slots=True)
class _Visit:
    last_seen: float
    turns: list[Turn] = field(default_factory=list)
    offered: set[int] = field(default_factory=set)


class Visits:
    def __init__(self, *, per_visitor: int = 20, per_day: int = 400, clock=time.monotonic) -> None:
        self.per_visitor, self.per_day, self._clock = per_visitor, per_day, clock
        self._visits: dict[str, _Visit] = {}
        self._asked: dict[str, deque[float]] = {}
        self._day: deque[float] = deque()
        self._lock = Lock()

    def _sweep(self, now: float) -> None:
        for key in [k for k, visit in self._visits.items() if now - visit.last_seen > VISIT_TTL_S]:
            del self._visits[key]
        for key in [
            k for k, times in self._asked.items() if not times or now - times[-1] > WINDOW_S
        ]:
            del self._asked[key]
        while self._day and now - self._day[0] > DAY_S:
            self._day.popleft()

    def open(self, visit_id: str | None) -> str:
        """The visit to continue, or a new one. An unknown or expired id is not
        an error: someone coming back after a pause should not see a failure."""
        now = self._clock()
        with self._lock:
            self._sweep(now)
            if visit_id is None or visit_id not in self._visits:
                visit_id = secrets.token_urlsafe(_ID_BYTES)
                self._visits[visit_id] = _Visit(now)
            self._visits[visit_id].last_seen = now
            return visit_id

    def admit(self, visit_id: str, address: str) -> Limit | None:
        """Count one question, or say when the next one may be asked.

        Both the visit and the address are counted, and the stricter wins:
        counting only the visit would let anyone reset their limit by opening
        a new tab.
        """
        now = self._clock()
        with self._lock:
            self._sweep(now)
            if len(self._day) >= self.per_day:
                return Limit("day", int(DAY_S - (now - self._day[0])) + 1)
            keys = (f"visit:{visit_id}", f"address:{address}")
            for key in keys:
                times = self._asked.setdefault(key, deque())
                while times and now - times[0] > WINDOW_S:
                    times.popleft()
                if len(times) >= self.per_visitor:
                    return Limit("visitor", int(WINDOW_S - (now - times[0])) + 1)
            for key in keys:
                self._asked[key].append(now)
            self._day.append(now)
            return None

    def turns(self, visit_id: str) -> tuple[Turn, ...]:
        with self._lock:
            visit = self._visits.get(visit_id)
            return tuple(visit.turns) if visit else ()

    def remember(self, visit_id: str, turn: Turn) -> None:
        with self._lock:
            visit = self._visits.get(visit_id)
            if visit is not None:
                visit.turns = [*visit.turns, turn][-MAX_TURNS:]

    def offer(self, visit_id: str, place_ids) -> None:
        """Record the candidates shown for an ambiguous name."""
        with self._lock:
            visit = self._visits.get(visit_id)
            if visit is not None:
                visit.offered = set(place_ids)

    def was_offered(self, visit_id: str, place_id: int) -> bool:
        """A `choice` must be one of the places this visit was shown. Otherwise
        the field would be a way to reach any place by guessing its id."""
        with self._lock:
            visit = self._visits.get(visit_id)
            return visit is not None and place_id in visit.offered
