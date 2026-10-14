"""The HTTP contract in `specs/002-hanjeok-guide-agent/contracts/guide-api.md`."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from tests.guide_fakes import ExportPlaces, FakePolicy, ScriptedModel, action, answer, replay_live

from guide.api import Snapshot, create_app
from guide.visits import Visits

QUESTION = "이번 토요일 가람궁 대신 조용한 곳 있어?"
CONGESTION = "hanjeok:congestion/101@2026-10-17"
SCRIPT = (
    action("congestion", place_id=101, date="2026-10-17"),
    action("alternatives", place_id=101, date="2026-10-17"),
    answer(
        "10월 17일 가람궁은 매우혼잡 예보입니다.", CONGESTION, "hanjeok:alternatives/101@2026-10-17"
    ),
)


class TestRuntime:
    __test__ = False

    def __init__(
        self, *replies, ready: bool = True, visits: Visits | None = None, model=None
    ) -> None:
        self.model = model or ScriptedModel(*replies)
        self.policy = FakePolicy()
        self.live = replay_live()
        self.visits = visits or Visits()
        self.checkpointer = InMemorySaver()
        self.callbacks = []
        self._ready = ready

    def snapshot(self):
        if not self._ready:
            return None
        places = ExportPlaces()
        return Snapshot(
            places,
            "gen-test",
            places.exported_at,
            "2026-10-10T09:00:00Z",
            {"places": 40, "related": 54, "events": 5, "regions": 2},
        )


def client(runtime) -> TestClient:
    return TestClient(create_app(runtime, origins=["https://agent.example"]))


def frames(response) -> list[tuple[str, dict]]:
    parsed = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


def ask(http: TestClient, **body):
    return http.post("/guide/ask", json={"question": QUESTION, **body})


def test_an_answered_question_streams_in_the_contracts_order():
    response = ask(client(TestRuntime(*SCRIPT)))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = frames(response)
    names = [name for name, _ in events]
    assert names[0] == "visit" and names[-3:] == ["answer", "path", "done"]
    assert set(names[1:-3]) == {"step"}
    visit = events[0][1]
    assert visit["visit_id"] and visit["as_of"] == {
        "export": "2026-10-13T02:00:00Z",
        "wiki": "2026-10-10T09:00:00Z",
    }
    done = events[-1][1]
    assert (
        done["outcome"] == "answered"
        and done["model"] == "scripted"
        and done["generated_at"].endswith("Z")
    )
    step = events[1][1]
    assert set(step) == {
        "index",
        "kind",
        "inputs",
        "status",
        "reason",
        "produced",
        "summary",
        "as_of",
    }


@pytest.mark.parametrize(
    ("question", "terminal", "cause"),
    [
        ("가람궁 입장료는 얼마야?", "stopped", "unsupported_topic"),
        ("은행나무길은 토요일에 붐벼?", "ask_user", "ambiguous_place"),
    ],
)
def test_every_stream_ends_with_exactly_one_terminal_event(question, terminal, cause):
    events = frames(client(TestRuntime()).post("/guide/ask", json={"question": question}))

    terminals = [name for name, _ in events if name in ("done", "ask_user", "stopped")]
    assert terminals == [terminal]
    assert events[-1][0] == terminal and events[-1][1]["cause"] == cause
    assert "answer" not in [name for name, _ in events]


def test_a_crash_inside_a_question_still_ends_the_stream_and_leaks_nothing():
    class Exploding(ScriptedModel):
        def decide(self, *args, **kwargs):
            raise RuntimeError("secret-internal-detail /srv/app/config.py")

    response = ask(client(TestRuntime(model=Exploding())))

    events = frames(response)
    assert events[-1][0] == "stopped"
    assert events[-1][1]["outcome"] == "failed"
    assert "secret-internal-detail" not in response.text and "Traceback" not in response.text


def test_choosing_a_candidate_continues_the_visit():
    runtime = TestRuntime(
        action("congestion", place_id=141, date="2026-10-17"),
        answer(
            "은행나무길(솔내구)은 혼잡 데이터가 없어 알 수 없습니다.",
            "hanjeok:congestion/141@2026-10-17",
        ),
    )
    http = client(runtime)
    question = "은행나무길은 토요일에 붐벼?"
    first = frames(http.post("/guide/ask", json={"question": question}))
    visit_id = first[0][1]["visit_id"]

    second = frames(
        http.post("/guide/ask", json={"question": question, "visit_id": visit_id, "choice": 141})
    )

    assert second[0][1]["visit_id"] == visit_id
    assert second[-1][0] == "done"


def test_a_choice_that_was_never_offered_is_a_bad_request():
    http = client(TestRuntime())
    visit_id = frames(ask(http, question="은행나무길은 토요일에 붐벼?"))[0][1]["visit_id"]

    response = ask(http, question="은행나무길은 토요일에 붐벼?", visit_id=visit_id, choice=101)

    assert response.status_code == 400
    assert response.json()["cause"] == "invalid_request"


def test_an_unknown_visit_id_is_replaced_not_rejected():
    events = frames(ask(client(TestRuntime(*SCRIPT)), visit_id="expired-or-made-up"))

    assert events[0][1]["visit_id"] != "expired-or-made-up"
    assert events[-1][0] == "done"


@pytest.mark.parametrize(
    "body",
    [
        {"question": "   "},
        {"question": "가" * 501},
        {},
        {"question": QUESTION, "strategy": "whole"},
        {"question": QUESTION, "visit_id": 7},
        {"question": QUESTION, "choice": "101"},
    ],
)
def test_bad_requests_are_400_with_the_contracts_body(body):
    response = client(TestRuntime()).post("/guide/ask", json=body)

    assert response.status_code == 400
    assert (
        set(response.json()) == {"cause", "detail"}
        and response.json()["cause"] == "invalid_request"
    )


def test_a_body_that_is_not_json_is_400():
    response = client(TestRuntime()).post(
        "/guide/ask", content=b"not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 400


def test_the_usage_limit_is_429_and_says_when_to_come_back():
    http = client(TestRuntime(*SCRIPT, visits=Visits(per_visitor=1)))
    assert ask(http).status_code == 200

    response = ask(http)

    assert response.status_code == 429
    body = response.json()
    assert (
        body["cause"] == "usage_limit" and body["scope"] == "visitor" and body["retry_after_s"] > 0
    )
    assert response.headers["retry-after"] == str(body["retry_after_s"])


def test_with_no_data_loaded_asking_is_503_and_status_says_not_ready():
    http = client(TestRuntime(ready=False))

    assert ask(http).status_code == 503
    assert ask(http).json()["cause"] == "not_ready"
    status = http.get("/guide/status").json()
    assert status["ready"] is False and status["generation"] is None
    assert http.get("/guide/places", params={"query": "가람"}).status_code == 503


def test_status_reports_the_refresh_record_without_credentials():
    status = client(TestRuntime()).get("/guide/status").json()

    assert status == {
        "ready": True,
        "as_of": {"export": "2026-10-13T02:00:00Z", "wiki": "2026-10-10T09:00:00Z"},
        "counts": {"places": 40, "related": 54, "events": 5, "regions": 2},
        "generation": "gen-test",
        "limits": {"per_visitor": 20, "per_day": 400},
    }


def test_places_are_found_by_name_exact_first_and_at_most_ten():
    http = client(TestRuntime())

    exact = http.get("/guide/places", params={"query": "은행나무길"}).json()
    many = http.get("/guide/places", params={"query": "솔내"}).json()

    assert [p["place_id"] for p in exact["places"]] == [140, 141]
    assert set(exact["places"][0]) == {"place_id", "name", "region", "has_congestion_data"}
    assert exact["as_of"] == "2026-10-13T02:00:00Z"
    assert len(many["places"]) <= 10


@pytest.mark.parametrize("query", ["", "   ", "가" * 51])
def test_a_place_query_outside_its_limits_is_400(query):
    assert client(TestRuntime()).get("/guide/places", params={"query": query}).status_code == 400


def test_a_place_and_its_neighbourhood_in_rank_order_with_no_congestion_value():
    body = client(TestRuntime()).get("/guide/places/101").json()

    assert body["place"]["name"] == "가람궁" and body["place"]["category"] == "역사 고궁"
    assert [(r["rank"], r["name"]) for r in body["related"]][:3] == [
        (1, "솔내 한옥마을"),
        (2, "물빛 서원"),
        (3, "달맞이 숲길"),
    ]
    assert [e["id"] for e in body["events"]] == ["festival:garam-night"]
    assert body["as_of"] == "2026-10-13T02:00:00Z"
    assert not {"grade", "concentration", "percentile"} & set(
        json.dumps(body).replace('"', " ").split()
    )


def test_an_unknown_place_is_404_and_a_non_numeric_id_is_not_a_500():
    http = client(TestRuntime())

    assert http.get("/guide/places/99999").status_code == 404
    assert http.get("/guide/places/99999").json() == {"cause": "unknown_place"}
    assert http.get("/guide/places/abc").status_code == 422


def test_cors_allows_only_the_configured_origin():
    http = client(TestRuntime())

    allowed = http.get("/guide/status", headers={"Origin": "https://agent.example"})
    other = http.get("/guide/status", headers={"Origin": "https://elsewhere.example"})

    assert allowed.headers["access-control-allow-origin"] == "https://agent.example"
    assert "access-control-allow-origin" not in other.headers


def test_production_refuses_to_start_without_an_origin(monkeypatch):
    from guide.api import allowed_origins

    monkeypatch.delenv("GUIDE_CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("GUIDE_ENV", "production")
    with pytest.raises(RuntimeError):
        allowed_origins()
    monkeypatch.setenv("GUIDE_CORS_ALLOWED_ORIGINS", "https://a.example, https://b.example")
    assert allowed_origins() == ["https://a.example", "https://b.example"]


def test_refresh_and_evaluation_are_not_reachable_over_http():
    http = client(TestRuntime())

    for path in ("/guide/refresh", "/guide/eval/run", "/docs", "/openapi.json"):
        assert http.post(path).status_code in (404, 405)
        assert http.get(path).status_code in (404, 405)


def test_the_evaluation_report_is_served_only_once_published(tmp_path):
    from guide.eval.store import ReportStore

    store = ReportStore(tmp_path)
    http = TestClient(create_app(TestRuntime(), origins=[], reports=store))

    assert http.get("/guide/eval/latest").status_code == 404
    assert http.get("/guide/eval/latest").json() == {"cause": "no_report"}

    store.put({"report_id": "r1", "question_count": 1}, {"q01": {"question_id": "q01"}})
    assert http.get("/guide/eval/latest").status_code == 404, "stored is not published"
    assert http.get("/guide/eval/r1").json()["report_id"] == "r1"

    store.publish("r1")
    assert http.get("/guide/eval/latest").json() == {"report_id": "r1", "question_count": 1}
    assert http.get("/guide/eval/r1/samples/q01").json() == {"question_id": "q01"}
    assert http.get("/guide/eval/r1/samples/q99").status_code == 404
    assert http.get("/guide/eval/..%2Fr1").status_code == 404


def test_the_report_is_readable_while_the_graph_is_down(tmp_path):
    from guide.eval.store import ReportStore

    store = ReportStore(tmp_path)
    store.put({"report_id": "r1"}, {})
    store.publish("r1")

    http = TestClient(create_app(TestRuntime(ready=False), origins=[], reports=store))

    assert http.get("/guide/eval/latest").status_code == 200


def test_a_follow_up_in_the_same_visit_knows_the_place_and_date():
    runtime = TestRuntime(
        *SCRIPT,
        action("events", place_id=101, date="2026-10-17"),
        answer("가람궁 달빛 야행이 열립니다.", "hanjeok:events/101@2026-10-17"),
    )
    http = client(runtime)
    visit_id = frames(ask(http))[0][1]["visit_id"]

    events = frames(
        http.post("/guide/ask", json={"question": "거기 그날 행사 있어?", "visit_id": visit_id})
    )

    assert events[-1][0] == "done"
    assert "2026-10-17" in runtime.model.calls[-1]["user"]


def test_an_expired_visits_questions_are_deleted_with_it():
    from guide.visits import VISIT_TTL_S

    now = [0.0]
    saver = InMemorySaver()
    runtime = TestRuntime(
        *SCRIPT, visits=Visits(clock=lambda: now[0], on_expire=saver.delete_thread)
    )
    runtime.checkpointer = saver
    http = client(runtime)
    visit_id = frames(ask(http))[0][1]["visit_id"]
    assert saver.get_tuple({"configurable": {"thread_id": visit_id}}) is not None

    now[0] += VISIT_TTL_S + 1
    runtime.visits.open(None)

    assert saver.get_tuple({"configurable": {"thread_id": visit_id}}) is None


def test_a_visit_survives_a_restart_when_checkpoints_are_kept_in_a_file(tmp_path, monkeypatch):
    from tests.guide_fakes import TODAY

    from guide.agent import Agent
    from guide.api import checkpointer_from_env

    monkeypatch.setenv("GUIDE_CHECKPOINT_DB", str(tmp_path / "visits" / "checkpoints.sqlite"))

    def agent(*replies):
        return Agent(
            ScriptedModel(*replies),
            ExportPlaces(),
            FakePolicy(),
            replay_live(),
            checkpointer=checkpointer_from_env(),
        )

    list(agent().stream("은행나무길은 토요일에 붐벼?", thread_id="v", today=TODAY))

    # A new saver over the same file, as a restarted process would open.
    after_restart = agent(
        action("congestion", place_id=140, date="2026-10-17"),
        answer("알 수 없습니다.", "hanjeok:place/140"),
    )
    assert [c["place_id"] for c in after_restart.pending("v")] == [140, 141]
    assert list(after_restart.stream(thread_id="v", resume=140))[-1][0] in ("done", "stopped")


def test_tracing_is_off_without_keys(monkeypatch):
    from guide.api import tracing_callbacks

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert tracing_callbacks() == []
