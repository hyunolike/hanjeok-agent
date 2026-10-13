"""One question end to end, with a scripted model and recorded Hanjeok responses."""

from __future__ import annotations

from datetime import date

from tests.guide_fakes import (
    TODAY,
    ExportPlaces,
    FakePolicy,
    ScriptedModel,
    action,
    answer,
    model_down,
    replay_live,
)

from guide.agent import MAX_LOOKUP_ROUNDS, SYSTEM, Agent
from guide.live import LiveClient, LiveError
from guide.scope import Turn

QUESTION = "이번 토요일 가람궁 대신 조용한 곳 있어?"
CONGESTION = "hanjeok:congestion/101@2026-10-17"
ALTERNATIVES = "hanjeok:alternatives/101@2026-10-17"
GOOD = answer(
    "10월 17일 가람궁은 매우혼잡 예보입니다. 한적이 정한 순서로 솔내 한옥마을, 물빛 서원, 달맞이 숲길이 대안입니다.",
    CONGESTION,
    ALTERNATIVES,
    "wiki:concepts/alternative-scoring.md",
)
LOOK_BOTH = (
    action("congestion", place_id=101, date="2026-10-17"),
    action("alternatives", place_id=101, date="2026-10-17"),
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def run(model, question=QUESTION, *, strategy="graph", live=None, clock=None, **kwargs):
    events: list[tuple[str, dict]] = []
    agent = Agent(
        model,
        ExportPlaces(),
        FakePolicy(),
        live or replay_live(),
        strategy=strategy,
        clock=clock or Clock(),
    )
    result = agent.ask(
        question, lambda name, data: events.append((name, data)), today=TODAY, **kwargs
    )
    return result, events


def names(events) -> list[str]:
    return [name for name, _ in events]


def finished_steps(events) -> list[dict]:
    return [data for name, data in events if name == "step" and data["status"] != "running"]


def test_answered_steps_then_answer_then_path_then_done():
    result, events = run(ScriptedModel(*LOOK_BOTH, GOOD))

    assert result.outcome == "answered"
    assert [s["kind"] for s in finished_steps(events)] == [
        "scope",
        "resolve",
        "congestion",
        "alternatives",
    ]
    assert [s["index"] for s in finished_steps(events)] == [0, 1, 2, 3]
    assert names(events)[-3:] == ["answer", "path", "done"]
    answer_event = dict(events)["answer"]
    assert [(c["id"], c["kind"]) for c in answer_event["citations"]] == [
        (CONGESTION, "record"),
        (ALTERNATIVES, "record"),
        ("wiki:concepts/alternative-scoring.md", "policy"),
    ]
    assert answer_event["citations"][0]["label"] == "가람궁 혼잡 예보 (10월 17일)"
    assert answer_event["partial"] is False
    assert result.model_calls == 3


def test_scope_and_resolve_are_emitted_before_the_model_is_asked_anything():
    seen_before_first_call: list[str] = []
    events: list[tuple[str, dict]] = []

    class Watching(ScriptedModel):
        def decide(self, *args, **kwargs):
            if not self.calls:
                seen_before_first_call.extend(
                    data["kind"] for name, data in events if name == "step"
                )
            return super().decide(*args, **kwargs)

    agent = Agent(
        Watching(GOOD_AFTER_RESOLVE), ExportPlaces(), FakePolicy(), replay_live(), clock=Clock()
    )
    agent.ask(QUESTION, lambda name, data: events.append((name, data)), today=TODAY)

    assert seen_before_first_call == ["scope", "resolve"]


GOOD_AFTER_RESOLVE = answer("가람궁은 한빛시 가람구의 옛 궁궐입니다.", "hanjeok:place/101")


def test_a_running_step_is_announced_with_the_index_its_result_replaces():
    _, events = run(ScriptedModel(*LOOK_BOTH, GOOD))

    steps = [data for name, data in events if name == "step"]
    running = [s for s in steps if s["status"] == "running"]
    assert [(s["kind"], s["index"]) for s in running] == [("congestion", 2), ("alternatives", 3)]
    for announced in running:
        final = next(
            s for s in steps if s["index"] == announced["index"] and s["status"] != "running"
        )
        assert final["kind"] == announced["kind"]


def test_no_answer_text_is_emitted_before_the_answer_event():
    _, events = run(ScriptedModel(*LOOK_BOTH, GOOD))

    before = events[: names(events).index("answer")]
    assert "대안입니다" not in repr(before)


def test_the_path_holds_exactly_what_the_lookups_returned():
    _, events = run(ScriptedModel(*LOOK_BOTH, GOOD))

    path = dict(events)["path"]
    places = sorted(n["label"] for n in path["nodes"] if n["kind"] == "place")
    assert places == ["가람궁", "달맞이 숲길", "물빛 서원", "솔내 한옥마을"]
    assert [(e["to"], e["rank"]) for e in path["edges"] if e["kind"] == "alternative"] == [
        ("hanjeok:place/118", 1),
        ("hanjeok:place/124", 2),
        ("hanjeok:place/131", 3),
    ]
    ids = {n["id"] for n in path["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in path["edges"])
    # 166 is related to 가람궁 in the graph, but no lookup returned it.
    assert "hanjeok:place/166" not in ids


def test_a_refused_lookup_is_a_visible_step_and_the_model_is_told_why():
    model = ScriptedModel(
        action("congestion", place_id=101, date="2026-12-25"),
        action("congestion", place_id=101, date="2026-10-17"),
        answer("10월 17일 가람궁은 매우혼잡 예보입니다.", CONGESTION),
    )

    result, events = run(model)

    refused = finished_steps(events)[2]
    assert (refused["status"], refused["inputs"]) == ("refused", {"place_id": 101})
    assert "까지만" in refused["reason"]
    assert "하지 못한 조회" in model.calls[1]["user"] and "까지만" in model.calls[1]["user"]
    assert result.outcome == "answered"


def test_an_answer_with_an_unfetched_citation_gets_one_repair():
    model = ScriptedModel(
        action("congestion", place_id=101, date="2026-10-17"),
        answer("달맞이 숲길이 가장 조용합니다.", "hanjeok:place/131"),
        answer("10월 17일 가람궁은 매우혼잡 예보입니다.", CONGESTION),
    )

    result, events = run(model)

    assert result.outcome == "answered"
    assert dict(events)["answer"]["text"] == "10월 17일 가람궁은 매우혼잡 예보입니다."
    assert "달맞이 숲길이 가장 조용합니다" not in repr(events), "the refused draft is never shown"
    repair = model.calls[2]
    assert "직전 답이 받아들여지지 않았습니다" in repair["user"]
    assert repair["schema"]["properties"]["action"]["enum"] == ["answer"], (
        "a repair cannot start new lookups"
    )


def test_two_unverifiable_answers_end_the_question_without_showing_either():
    model = ScriptedModel(
        action("congestion", place_id=101, date="2026-10-17"),
        answer("첫 번째 초안", "hanjeok:place/999"),
        answer("두 번째 초안"),
    )

    result, events = run(model)

    assert (result.outcome, result.cause) == ("failed", "invalid_citations")
    assert names(events)[-1] == "stopped"
    assert "answer" not in names(events)
    assert "초안" not in repr(events)
    assert result.model_calls == 3


def test_after_three_lookups_the_model_can_only_answer():
    model = ScriptedModel(
        *LOOK_BOTH,
        action("events", place_id=101, date="2026-10-17"),
        GOOD,
    )

    result, _ = run(model)

    assert result.outcome == "answered"
    assert [len(c["schema"]["properties"]["action"]["enum"]) > 1 for c in model.calls] == [
        True,
        True,
        True,
        False,
    ]
    assert "조회는 더 할 수 없습니다" in model.calls[MAX_LOOKUP_ROUNDS]["user"]
    assert result.partial is False, "using the rounds is not running out of time"


def test_running_short_of_time_withdraws_the_lookups_and_marks_the_answer_partial():
    clock = Clock()

    class Slow(ScriptedModel):
        def decide(self, *args, **kwargs):
            clock.now += 26
            return super().decide(*args, **kwargs)

    model = Slow(*LOOK_BOTH, answer("10월 17일 가람궁은 매우혼잡 예보입니다.", CONGESTION))

    result, events = run(model, clock=clock)

    assert result.outcome == "answered"
    assert dict(events)["answer"]["partial"] is True
    assert model.calls[2]["schema"]["properties"]["action"]["enum"] == ["answer"]
    assert 0 < model.calls[2]["timeout"] <= 8


def test_no_time_left_at_all_is_budget_exhausted():
    clock = Clock()

    class VerySlow(ScriptedModel):
        def decide(self, *args, **kwargs):
            clock.now += 61
            return super().decide(*args, **kwargs)

    result, events = run(
        VerySlow(action("congestion", place_id=101, date="2026-10-17")), clock=clock
    )

    assert (result.outcome, result.cause) == ("failed", "budget_exhausted")
    assert dict(events)["stopped"]["message"]


def test_hanjeok_unreachable_with_nothing_live_fetched_stops_instead_of_guessing():
    class Down(LiveClient):
        def __init__(self) -> None:
            pass

        def today(self) -> date:
            return TODAY

        def congestion(self, place_id, day):
            raise LiveError("service_unreachable")

    result, events = run(
        ScriptedModel(action("congestion", place_id=101, date="2026-10-17")), live=Down()
    )

    assert (result.outcome, result.cause) == ("failed", "service_unreachable")
    assert finished_steps(events)[-1]["status"] == "failed"
    assert "answer" not in names(events)


def test_the_model_being_unavailable_is_a_failure_with_no_provider_text():
    result, events = run(ScriptedModel(model_down("authentication")))

    stopped = dict(events)["stopped"]
    assert (result.outcome, result.cause) == ("failed", "model_failed")
    assert "authentication" not in stopped["message"]


def test_a_declined_question_spends_no_model_call():
    model = ScriptedModel()

    result, events = run(model, "가람궁 입장료는 얼마야?")

    assert (result.outcome, result.cause) == ("declined", "unsupported_topic")
    assert names(events) == ["step", "stopped"]
    assert events[0][1]["status"] == "refused"
    assert model.calls == []


def test_an_ambiguous_name_asks_the_visitor_and_spends_no_model_call():
    model = ScriptedModel()

    result, events = run(model, "은행나무길은 토요일에 붐벼?")

    assert result.outcome == "ask_user"
    assert result.candidates == (140, 141)
    assert names(events) == ["step", "ask_user"]
    assert [c["place_id"] for c in events[-1][1]["candidates"]] == [140, 141]
    assert model.calls == []


def test_choosing_a_candidate_resumes_the_same_question():
    model = ScriptedModel(
        action("congestion", place_id=141, date="2026-10-17"),
        answer(
            "은행나무길(솔내구)은 혼잡 데이터가 없어 알 수 없습니다.",
            "hanjeok:congestion/141@2026-10-17",
        ),
    )

    result, events = run(model, "은행나무길은 토요일에 붐벼?", choice=141)

    assert result.outcome == "answered"
    assert result.place_ids == (141,)
    assert finished_steps(events)[2]["status"] == "no_data"


def test_an_answer_with_nothing_fetched_is_no_grounds_and_is_not_shown():
    model = ScriptedModel(action("search_places", text="zzzz"), answer("아무 곳이나 가세요."))

    result, events = run(model, "조용한 곳 추천해 줘")

    assert (result.outcome, result.cause) == ("no_grounds", "no_grounds")
    assert "아무 곳이나" not in repr(events)


def test_a_follow_up_takes_its_place_and_date_from_the_earlier_question():
    turns = (Turn(QUESTION, (101,), ("2026-10-17",)),)
    model = ScriptedModel(
        action("events", place_id=101, date="2026-10-17"),
        answer("가람궁 달빛 야행이 열립니다.", "hanjeok:events/101@2026-10-17"),
    )

    result, _ = run(model, "거기 그날 행사 있어?", turns=turns)

    assert result.outcome == "answered"
    assert (result.place_ids, result.dates) == ((101,), ("2026-10-17",))
    assert "2026-10-17" in model.calls[0]["user"]


def test_the_two_strategies_show_the_model_the_same_thing_except_the_offered_lookups():
    reply = answer("가람궁은 한빛시 가람구의 옛 궁궐입니다.", "hanjeok:place/101")
    graph_model, vector_model = ScriptedModel(reply), ScriptedModel(reply)
    run(graph_model, strategy="graph")
    run(vector_model, strategy="vector")

    graph_call, vector_call = graph_model.calls[0], vector_model.calls[0]
    assert graph_call["system"] == vector_call["system"] == SYSTEM
    differing = set(graph_call["user"].splitlines()) ^ set(vector_call["user"].splitlines())
    assert len(differing) == 1 and next(iter(differing)).startswith("- related_places(")
    graph_actions = set(graph_call["schema"]["properties"]["action"]["enum"])
    vector_actions = set(vector_call["schema"]["properties"]["action"]["enum"])
    assert graph_actions - vector_actions == {"related_places"}
    assert vector_actions <= graph_actions


def test_the_prompt_never_shows_the_model_a_raw_grade_token():
    model = ScriptedModel(*LOOK_BOTH, GOOD)
    run(model)

    shown = "\n".join(call["user"] for call in model.calls)
    assert "매우혼잡" in shown
    assert not any(token in shown for token in ("VERY_CROWDED", "RELAXED", "NORMAL", "CROWDED"))


def test_internal_place_ids_are_removed_from_the_answer_text():
    reply = answer(
        "달맞이 숲길(place_id 131)으로 가세요. 솔내 한옥마을, place_id 118 도 있습니다.",
        ALTERNATIVES,
    )

    _, events = run(ScriptedModel(action("alternatives", place_id=101, date="2026-10-17"), reply))

    assert dict(events)["answer"]["text"] == "달맞이 숲길으로 가세요. 솔내 한옥마을 도 있습니다."


def test_the_kind_of_model_failure_and_gate_refusals_are_kept_for_the_record():
    failed, _ = run(ScriptedModel(model_down("rate_limit")))
    refused, _ = run(ScriptedModel(answer("초안", "hanjeok:place/999"), answer("초안")))

    assert failed.model_failure == "rate_limit"
    assert len(refused.rejections) == 2 and "조회한 id 가 아닙니다" in refused.rejections[0]
