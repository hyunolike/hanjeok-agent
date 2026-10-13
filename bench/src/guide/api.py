"""The guide's HTTP surface. Contract: `specs/002-hanjeok-guide-agent/contracts/guide-api.md`.

Read-only towards Hanjeok and the wiki. Refresh and evaluation are not here:
they rebuild the graph or spend model quota, and this demo has no
authentication to put in front of that. They are `guide` commands instead.

No response carries a stack trace or a provider's message. A failure is one of
a fixed list of causes with a sentence written for the visitor.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from guide.agent import Agent
from guide.live import LiveClient, Recording
from guide.model import Model
from guide.scope import Turn
from guide.sources import Places, Policy
from guide.visits import Visits

log = logging.getLogger("guide")

STRATEGIES = ("graph", "vector")
TERMINAL = ("done", "ask_user", "stopped")
INTERNAL_MESSAGE = "안내 서버에서 문제가 생겨 답하지 못했습니다. 잠시 뒤에 다시 물어봐 주세요."


@dataclass(frozen=True, slots=True)
class Snapshot:
    """The copy of the data one request reads, from start to finish."""

    places: Places
    generation: str
    exported_at: str
    wiki_as_of: str
    counts: dict[str, int]


class Runtime(Protocol):
    visits: Visits
    live: LiveClient
    model: Model
    policy: Policy

    def snapshot(self) -> Snapshot | None:
        """`None` when there is no active generation or the graph cannot be reached."""


def _error(status: int, cause: str, **extra: Any) -> JSONResponse:
    headers = {"Retry-After": str(extra["retry_after_s"])} if "retry_after_s" in extra else None
    return JSONResponse({"cause": cause, **extra}, status_code=status, headers=headers)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _address(request: Request) -> str:
    # Behind a proxy every visitor would share the proxy's address. The header
    # is trusted only when the deployment says a proxy it controls sets it.
    if os.environ.get("GUIDE_TRUST_PROXY") == "1":
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def _place_hit(place) -> dict:
    return {
        "place_id": place.id,
        "name": place.name,
        "region": place.region_label or "",
        "has_congestion_data": place.has_congestion_data,
    }


def allowed_origins() -> list[str]:
    configured = [
        o.strip() for o in os.environ.get("GUIDE_CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ]
    if configured:
        return configured
    if os.environ.get("GUIDE_ENV") == "production":
        # A default here would be either too open or silently wrong.
        raise RuntimeError("GUIDE_CORS_ALLOWED_ORIGINS is required in production")
    return ["http://localhost:3000"]


def create_app(runtime: Runtime | None = None, *, origins: list[str] | None = None) -> FastAPI:
    state: dict[str, Any] = {"runtime": runtime}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = state["runtime"] is None
        if owned:
            state["runtime"] = EnvRuntime()
        yield
        if owned:
            state["runtime"].close()

    app = FastAPI(
        title="Hanjeok guide", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins is not None else allowed_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "accept"],
    )

    def ready() -> tuple[Runtime, Snapshot | None]:
        current: Runtime = state["runtime"]
        try:
            return current, current.snapshot()
        except Exception:
            log.exception("graph unreachable")
            return current, None

    @app.post("/guide/ask")
    async def ask(request: Request):
        try:
            body = await request.json()
        except ValueError:
            return _error(400, "invalid_request", detail="body is not JSON")
        if not isinstance(body, dict):
            return _error(400, "invalid_request", detail="body is not an object")
        question = body.get("question")
        question = question.strip() if isinstance(question, str) else ""
        if not 1 <= len(question) <= 500:
            return _error(400, "invalid_request", detail="question must be 1 to 500 characters")
        strategy = body.get("strategy") or "graph"
        if strategy not in STRATEGIES:
            return _error(400, "invalid_request", detail="strategy must be graph or vector")
        visit_id = body.get("visit_id")
        if visit_id is not None and not isinstance(visit_id, str):
            return _error(400, "invalid_request", detail="visit_id must be a string or null")
        choice = body.get("choice")
        if choice is not None and (not isinstance(choice, int) or isinstance(choice, bool)):
            return _error(400, "invalid_request", detail="choice must be a place id or null")

        current, snapshot = ready()
        if snapshot is None:
            return _error(503, "not_ready", detail="no data is loaded")

        visits = current.visits
        visit = visits.open(visit_id)
        if choice is not None and not visits.was_offered(visit, choice):
            return _error(
                400, "invalid_request", detail="choice is not one of the offered candidates"
            )
        limit = visits.admit(visit, _address(request))
        if limit is not None:
            return _error(429, "usage_limit", scope=limit.scope, retry_after_s=limit.retry_after_s)

        def stream() -> Iterator[str]:
            yield _sse(
                "visit",
                {
                    "visit_id": visit,
                    "as_of": {"export": snapshot.exported_at, "wiki": snapshot.wiki_as_of},
                },
            )
            events: queue.Queue[tuple[str, dict] | None] = queue.Queue()

            def work() -> None:
                try:
                    agent = Agent(
                        current.model,
                        snapshot.places,
                        current.policy,
                        current.live,
                        strategy=strategy,
                    )
                    result = agent.ask(
                        question,
                        lambda name, data: events.put((name, data)),
                        turns=visits.turns(visit),
                        choice=choice,
                    )
                    if result.outcome == "ask_user":
                        visits.offer(visit, result.candidates)
                    elif result.outcome == "answered":
                        visits.remember(visit, Turn(question, result.place_ids, result.dates))
                except Exception:
                    # Logged here; the visitor gets a cause, not the exception.
                    log.exception("question failed")
                finally:
                    events.put(None)

            threading.Thread(target=work, daemon=True).start()
            ended = False
            while (item := events.get()) is not None:
                if ended:
                    continue
                ended = item[0] in TERMINAL
                yield _sse(*item)
            if not ended:
                # Every stream ends with exactly one terminal event, including
                # the ones that end because something broke.
                yield _sse(
                    "stopped",
                    {
                        "outcome": "failed",
                        "cause": "service_unreachable",
                        "message": INTERNAL_MESSAGE,
                    },
                )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/guide/places")
    def places(query: str = ""):
        query = query.strip()
        if not 1 <= len(query) <= 50:
            return _error(400, "invalid_request", detail="query must be 1 to 50 characters")
        _, snapshot = ready()
        if snapshot is None:
            return _error(503, "not_ready", detail="no data is loaded")
        found = snapshot.places.match_name(query)
        return {"places": [_place_hit(place) for place in found], "as_of": snapshot.exported_at}

    @app.get("/guide/places/{place_id}")
    def place(place_id: int):
        _, snapshot = ready()
        if snapshot is None:
            return _error(503, "not_ready", detail="no data is loaded")
        found = snapshot.places.detail(place_id)
        if found is None:
            return _error(404, "unknown_place")
        category = " ".join(part for part in (found.category_mid, found.category_small) if part)
        return {
            # No congestion value: it is date-bound and only a question fetches it.
            "place": {
                **_place_hit(found),
                "category": category or None,
                "overview": found.overview or found.summary,
            },
            "related": [
                {
                    "place_id": row.place.id,
                    "name": row.place.name,
                    "region": row.place.region_label or "",
                    # Position in Hanjeok's order, so an unranked link still has a place in it.
                    "rank": position,
                }
                for position, row in enumerate(snapshot.places.related(place_id, limit=10), start=1)
            ],
            "events": [
                {
                    "id": event.id,
                    "name": event.name,
                    "start_date": event.start_date,
                    "end_date": event.end_date,
                }
                for event in snapshot.places.events(place_id, on=None)
            ],
            "as_of": snapshot.exported_at,
        }

    @app.get("/guide/status")
    def status():
        current, snapshot = ready()
        limits = {"per_visitor": current.visits.per_visitor, "per_day": current.visits.per_day}
        if snapshot is None:
            return {
                "ready": False,
                "as_of": {"export": None, "wiki": None},
                "counts": {"places": 0, "related": 0, "events": 0, "regions": 0},
                "generation": None,
                "limits": limits,
            }
        return {
            "ready": True,
            "as_of": {"export": snapshot.exported_at, "wiki": snapshot.wiki_as_of or None},
            "counts": snapshot.counts,
            "generation": snapshot.generation,
            "limits": limits,
        }

    return app


class EnvRuntime:
    """The real wiring: local Neo4j, the local embedding model, NVIDIA, Hanjeok.

    Nothing heavy happens here. The embedding model loads on the first search
    and the chat client on the first question, so the status endpoint answers
    as soon as the process is up.
    """

    def __init__(self) -> None:
        from bench.embeddings import LocalEmbedder
        from bench.graph.store import driver_from_env
        from guide.model import GuideModel
        from guide.sources import GraphPolicy

        self._driver = driver_from_env()
        self._embedder = LocalEmbedder()
        self._gazetteers: dict[str, dict] = {}
        self.model = GuideModel()
        self.policy = GraphPolicy(self._driver, self._embedder)
        self.visits = Visits(
            per_visitor=int(os.environ.get("GUIDE_LIMIT_PER_VISITOR", "20")),
            per_day=int(os.environ.get("GUIDE_LIMIT_PER_DAY", "400")),
        )
        mode = os.environ.get("GUIDE_LIVE_MODE", "live")
        directory = os.environ.get("GUIDE_LIVE_RECORDING") or (
            str(Path("tests") / "fixtures" / "hanjeok-live") if mode == "replay" else ""
        )
        self.live = LiveClient(
            mode=mode,
            base_url=os.environ.get("HANJEOK_BASE_URL", ""),
            recording=Recording(directory) if directory else None,
        )

    def snapshot(self) -> Snapshot | None:
        from bench.graph.store import session
        from guide.graph import read
        from guide.sources import WIKI_CORPUS, GraphPlaces, group_gazetteer

        active = read.active(self._driver)
        if active is None:
            return None
        if active.generation not in self._gazetteers:
            # One generation's names, read once. The old generation's entry is
            # dropped so a long-running process does not keep every copy.
            self._gazetteers = {
                active.generation: group_gazetteer(read.gazetteer(self._driver, active.generation))
            }
        with session(self._driver) as s:
            row = s.run(
                "MATCH (c:Corpus {name: $name}) RETURN c.loaded_at AS at", name=WIKI_CORPUS
            ).single()
        return Snapshot(
            GraphPlaces(self._driver, active, self._embedder, self._gazetteers[active.generation]),
            active.generation,
            active.exported_at,
            (row["at"] if row else "") or "",
            active.counts,
        )

    def close(self) -> None:
        self._driver.close()


def __getattr__(name: str):
    # `uvicorn guide.api:app` builds the app on first access, so importing this
    # module in a test does not read the environment or open a connection.
    if name == "app":
        return create_app()
    raise AttributeError(name)
