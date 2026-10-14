"""The guide as an MCP server, so another program can ask it.

The HTTP API is for the demo's own screen. This is for a caller that speaks the
Model Context Protocol instead: an assistant, another agent, or — the reason it
exists — the Hanjeok backend, whose Spring AI has an MCP client. One protocol,
and the caller needs no knowledge of this service's event stream.

Four tools, all read-only. `ask_guide` runs the same agent the API runs, with
the same rules: lookups from a fixed set, an answer that cites only what it
fetched, a visit that can be asked which place was meant. The other three read
the graph directly and involve no model.

Not exposed, here as over HTTP: refreshing the data and running an evaluation.
"""

from __future__ import annotations

from datetime import date as day

from mcp.server.mcpserver import MCPServer

from guide.agent import Agent
from guide.api import Runtime

INSTRUCTIONS = (
    "한적 여행 서비스의 장소, 혼잡 예보, 대안 장소에 대해 답합니다. "
    "ask_guide 의 답은 citations 에 있는 근거만으로 쓰였습니다. "
    "outcome 이 ask_user 이면 candidates 중 하나의 place_id 를 choice 로, "
    "받은 visit_id 와 함께 다시 불러 주세요. 장소의 순서는 한적이 정한 것이며 바꾸지 마세요."
)
# Every caller over MCP shares one address for the usage limit: the protocol
# gives no address of its own, and the daily limit still bounds the total.
MCP_ADDRESS = "mcp"


def _place(row) -> dict:
    return {
        "place_id": row.id,
        "name": row.name,
        "region": row.region_label or "",
        "has_congestion_data": row.has_congestion_data,
    }


def build_server(runtime: Runtime) -> MCPServer:
    server = MCPServer("hanjeok-guide", instructions=INSTRUCTIONS)

    def snapshot():
        current = runtime.snapshot()
        if current is None:
            raise RuntimeError("not_ready: no data is loaded")
        return current

    @server.tool()
    def ask_guide(
        question: str,
        visit_id: str | None = None,
        choice: int | None = None,
        place_id: int | None = None,
        date: str | None = None,
    ) -> dict:
        """한적의 장소와 혼잡에 대해 묻습니다. 예: "이번 토요일 경복궁 대신 조용한 곳 있어?"

        visit_id 를 다시 보내면 앞 질문의 장소와 날짜를 이어서 씁니다.
        outcome 이 ask_user 였다면 choice 에 고른 place_id 를 넣어 다시 부릅니다.
        place_id 와 date(YYYY-MM-DD)는 호출하는 쪽이 이미 아는 장소와 날짜입니다.
        질문에 장소나 날짜가 없을 때만 씁니다.
        """
        question = question.strip()
        if not 1 <= len(question) <= 500:
            return {
                "outcome": "failed",
                "cause": "invalid_request",
                "message": "question 은 1~500자입니다.",
            }
        if date is not None:
            try:
                day.fromisoformat(date)
            except ValueError:
                return {
                    "outcome": "failed",
                    "cause": "invalid_request",
                    "message": "date 는 YYYY-MM-DD 입니다.",
                }
        context = {k: v for k, v in (("place_id", place_id), ("date", date)) if v is not None}
        current = snapshot()
        visit = runtime.visits.open(visit_id)
        agent = Agent(
            runtime.model,
            current.places,
            runtime.policy,
            runtime.live,
            checkpointer=runtime.checkpointer,
            callbacks=runtime.callbacks,
        )
        if choice is not None:
            offered = [c["place_id"] for c in agent.pending(visit) or []]
            if choice not in offered:
                return {
                    "outcome": "failed",
                    "cause": "invalid_request",
                    "message": "choice 는 이 visit 에서 받은 candidates 중 하나여야 합니다.",
                    "visit_id": visit,
                }
        limit = runtime.visits.admit(visit, MCP_ADDRESS)
        if limit is not None:
            return {
                "outcome": "failed",
                "cause": "usage_limit",
                "scope": limit.scope,
                "retry_after_s": limit.retry_after_s,
                "visit_id": visit,
            }

        events = list(agent.stream(question, thread_id=visit, resume=choice, context=context))
        result = agent.result
        reply: dict = {
            "outcome": result.outcome,
            "cause": result.cause,
            "visit_id": visit,
            "as_of": current.exported_at,
            # What was looked up, in order. A caller can show these or not; an
            # answer without them would be a claim with nothing behind it.
            "steps": [
                {"kind": step["kind"], "status": step["status"], "summary": step["summary"]}
                for step in result.steps
            ],
        }
        for name, data in events:
            if name == "answer":
                reply |= {
                    "answer": data["text"],
                    "citations": data["citations"],
                    "partial": data["partial"],
                }
            elif name == "ask_user":
                reply |= {"prompt": data["prompt"], "candidates": data["candidates"]}
            elif name == "stopped":
                reply["message"] = data["message"]
        return reply

    @server.tool()
    def find_places(name: str) -> list[dict]:
        """이름으로 장소를 찾습니다. 공백은 무시하고, 같은 이름 → 앞이 같은 이름 → 포함하는 이름 순으로 최대 10곳."""
        name = name.strip()
        if not 1 <= len(name) <= 50:
            return []
        return [_place(row) for row in snapshot().places.match_name(name)]

    @server.tool()
    def place_neighbourhood(place_id: int) -> dict:
        """장소 하나와, 한적이 그곳과 이어 둔 장소(한적의 순위 순서), 그곳의 행사.

        혼잡도 값은 없습니다. 날짜에 묶인 값이라 ask_guide 로 날짜와 함께 물어야 합니다.
        """
        places = snapshot().places
        found = places.detail(place_id)
        if found is None:
            return {"cause": "unknown_place"}
        return {
            "place": {**_place(found), "overview": found.overview or found.summary},
            "related": [
                {**_place(row.place), "rank": position}
                for position, row in enumerate(places.related(place_id, limit=10), start=1)
            ],
            "events": [
                {"id": e.id, "name": e.name, "start_date": e.start_date, "end_date": e.end_date}
                for e in places.events(place_id, on=None)
            ],
        }

    @server.tool()
    def guide_status() -> dict:
        """데이터가 실려 있는지, 언제 내보낸 것인지, 몇 곳인지."""
        current = runtime.snapshot()
        if current is None:
            return {"ready": False}
        return {
            "ready": True,
            "export_as_of": current.exported_at,
            "generation": current.generation,
            "counts": current.counts,
        }

    return server
