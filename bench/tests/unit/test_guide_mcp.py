"""The guide's MCP tools, called the way an MCP client's request reaches them."""

from __future__ import annotations

import asyncio
import json

from tests.contract.test_guide_api_contract import TestRuntime
from tests.guide_fakes import action, answer

from guide.mcp_server import build_server
from guide.visits import Visits

CONGESTION = "hanjeok:congestion/101@2026-10-17"


def call(runtime, tool: str, **arguments):
    result = asyncio.run(build_server(runtime).call_tool(tool, arguments))
    assert result.is_error is False, result
    parts = [json.loads(part.text) for part in result.content]
    return parts[0] if len(parts) == 1 else parts


def test_the_server_offers_four_read_only_tools_and_nothing_that_changes_anything():
    tools = asyncio.run(build_server(TestRuntime()).list_tools())

    assert {t.name for t in tools} == {
        "ask_guide",
        "find_places",
        "place_neighbourhood",
        "guide_status",
    }
    assert all(t.description for t in tools)
    assert not any(word in t.name for t in tools for word in ("refresh", "eval", "delete", "write"))


def test_asking_returns_the_verified_answer_with_what_it_rests_on():
    runtime = TestRuntime(
        action("congestion", place_id=101, date="2026-10-17"),
        answer("10월 17일 가람궁은 매우혼잡 예보입니다.", CONGESTION),
    )

    reply = call(runtime, "ask_guide", question="이번 토요일 가람궁 얼마나 붐벼?")

    assert reply["outcome"] == "answered"
    assert reply["answer"] == "10월 17일 가람궁은 매우혼잡 예보입니다."
    assert [(c["id"], c["kind"]) for c in reply["citations"]] == [(CONGESTION, "record")]
    assert [s["kind"] for s in reply["steps"]] == ["scope", "resolve", "congestion"]
    assert reply["visit_id"] and reply["as_of"] == "2026-10-13T02:00:00Z"


def test_an_ambiguous_name_comes_back_as_candidates_and_a_choice_resumes_it():
    runtime = TestRuntime(
        action("congestion", place_id=141, date="2026-10-17"),
        answer(
            "은행나무길(솔내구)은 혼잡 데이터가 없어 알 수 없습니다.",
            "hanjeok:congestion/141@2026-10-17",
        ),
    )
    question = "은행나무길은 토요일에 붐벼?"

    first = call(runtime, "ask_guide", question=question)
    assert first["outcome"] == "ask_user"
    assert [c["place_id"] for c in first["candidates"]] == [140, 141]
    assert "answer" not in first

    second = call(runtime, "ask_guide", question=question, visit_id=first["visit_id"], choice=141)
    assert second["outcome"] == "answered"
    assert second["visit_id"] == first["visit_id"]


def test_a_choice_that_was_not_offered_is_refused_without_running_anything():
    runtime = TestRuntime()
    first = call(runtime, "ask_guide", question="은행나무길은 토요일에 붐벼?")

    reply = call(runtime, "ask_guide", question="x", visit_id=first["visit_id"], choice=101)

    assert (reply["outcome"], reply["cause"]) == ("failed", "invalid_request")
    assert runtime.model.calls == []


def test_a_declined_question_says_why():
    reply = call(TestRuntime(), "ask_guide", question="가람궁 입장료는 얼마야?")

    assert (reply["outcome"], reply["cause"]) == ("declined", "unsupported_topic")
    assert "알려 드릴 수 있습니다" in reply["message"]
    assert "answer" not in reply


def test_the_usage_limit_applies_over_mcp_too():
    runtime = TestRuntime(visits=Visits(per_visitor=1))
    call(runtime, "ask_guide", question="가람궁 입장료는 얼마야?")

    reply = call(runtime, "ask_guide", question="가람궁 입장료는 얼마야?")

    assert reply["cause"] == "usage_limit" and reply["retry_after_s"] > 0


def test_places_are_found_by_name_and_a_neighbourhood_is_in_rank_order():
    runtime = TestRuntime()

    found = call(runtime, "find_places", name="은행나무길")
    around = call(runtime, "place_neighbourhood", place_id=101)

    assert [p["place_id"] for p in found] == [140, 141]
    assert [(r["rank"], r["name"]) for r in around["related"]][:3] == [
        (1, "솔내 한옥마을"),
        (2, "물빛 서원"),
        (3, "달맞이 숲길"),
    ]
    assert not {"grade", "concentration"} & set(json.dumps(around).replace('"', " ").split())
    assert call(runtime, "place_neighbourhood", place_id=99999) == {"cause": "unknown_place"}


def test_status_says_when_nothing_is_loaded():
    assert call(TestRuntime(ready=False), "guide_status") == {"ready": False}
    assert call(TestRuntime(), "guide_status")["counts"]["places"] == 40


def test_a_caller_can_say_which_place_and_day_it_is_looking_at():
    runtime = TestRuntime(
        action("congestion", place_id=101, date="2026-10-17"),
        answer("10월 17일 가람궁은 매우혼잡 예보입니다.", CONGESTION),
    )

    reply = call(runtime, "ask_guide", question="여기 붐벼?", place_id=101, date="2026-10-17")

    assert reply["outcome"] == "answered"
    assert call(TestRuntime(), "ask_guide", question="여기 붐벼?", date="17 Oct")["cause"] == (
        "invalid_request"
    )
