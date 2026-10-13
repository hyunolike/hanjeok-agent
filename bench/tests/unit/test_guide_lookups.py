"""Each lookup: what it returns, what it refuses, and what becomes citable."""

from __future__ import annotations

import pytest
from tests.guide_fakes import TODAY, ExportPlaces, FakePolicy, replay_live

from guide.live import LiveClient, LiveError
from guide.lookups import LOOKUPS, Lookups, offered


def lookups(
    strategy: str = "graph", *, known: tuple[int, ...] = (101,), live=None, policy=None
) -> Lookups:
    places = ExportPlaces()
    made = Lookups(
        places, policy or FakePolicy(), live or replay_live(), today=TODAY, strategy=strategy
    )
    for place_id in known:
        made.add_place(places.detail(place_id))
    return made


def test_the_two_strategies_differ_by_exactly_one_lookup():
    assert set(offered("graph")) - set(offered("vector")) == {"related_places"}
    assert set(offered("vector")) <= set(offered("graph")) == set(LOOKUPS)
    with pytest.raises(ValueError):
        offered("whole")


def test_search_returns_at_most_five_places_and_makes_them_usable():
    subject = lookups(known=())

    outcome = subject.run("search_places", {"text": "숲길"})

    assert outcome.status == "ok"
    assert 1 <= len(outcome.produced) <= 5
    assert all(p.startswith("hanjeok:place/") for p in outcome.produced)
    assert 131 in subject.fetched.place_ids
    assert outcome.as_of == "2026-10-13T02:00:00Z"


def test_search_can_be_narrowed_to_a_region():
    subject = lookups(known=())
    subject.run("search_places", {"text": "공원", "region_code": "11140"})

    regions = {node["region"] for node in subject.fetched.nodes.values() if node["kind"] == "place"}
    assert regions == {"한빛시 솔내구"}


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"text": "  "},
        {"text": "가" * 101},
        {"text": "숲", "region_code": "서울"},
        {"text": "숲", "region_code": "1111"},
    ],
)
def test_search_refuses_inputs_outside_its_limits(args):
    outcome = lookups().run("search_places", args)

    assert outcome.status == "refused"
    assert outcome.reason and outcome.produced == ()


def test_search_that_finds_nothing_is_no_data_not_a_failure():
    assert lookups().run("search_places", {"text": "zzzz"}).status == "no_data"


def test_a_place_cannot_be_reached_by_guessing_its_id():
    subject = lookups(known=(101,))

    for name, args in (
        ("place_detail", {"place_id": 124}),
        ("related_places", {"place_id": 124}),
        ("congestion", {"place_id": 124, "date": "2026-10-17"}),
        ("alternatives", {"place_id": 124, "date": "2026-10-17"}),
        ("events", {"place_id": 124}),
    ):
        outcome = subject.run(name, args)
        assert outcome.status == "refused", name
        assert "아직 나오지 않은 장소" in outcome.reason
    assert subject.fetched.place_ids == {101}


@pytest.mark.parametrize("place_id", [None, "101", True, 1.5])
def test_a_place_id_that_is_not_an_integer_is_refused(place_id):
    assert lookups().run("place_detail", {"place_id": place_id}).status == "refused"


def test_related_places_come_numbered_in_hanjeoks_order_and_become_usable():
    subject = lookups()

    outcome = subject.run("related_places", {"place_id": 101, "limit": 3})

    passage = next(p for p in subject.fetched.passages if p.id == "hanjeok:related/101")
    assert passage.text.splitlines()[1:] == [
        "1. 솔내 한옥마을 (한빛시 가람구, place_id 118)",
        "2. 물빛 서원 (한빛시 솔내구, place_id 124)",
        "3. 달맞이 숲길 (한빛시 솔내구, place_id 131)",
    ]
    assert outcome.produced[:4] == (
        "hanjeok:related/101",
        "hanjeok:place/118",
        "hanjeok:place/124",
        "hanjeok:place/131",
    )
    assert "wiki:concepts/alternative-scoring.md" in outcome.produced
    assert {118, 124, 131} <= subject.fetched.place_ids
    ranked = [(e["to"], e["rank"]) for e in subject.fetched.edges if e["kind"] == "related"]
    assert ranked == [("hanjeok:place/118", 1), ("hanjeok:place/124", 2), ("hanjeok:place/131", 3)]


@pytest.mark.parametrize("limit", [0, 11, "3", True])
def test_related_places_refuses_a_limit_outside_one_to_ten(limit):
    assert lookups().run("related_places", {"place_id": 101, "limit": limit}).status == "refused"


def test_the_vector_strategy_cannot_follow_relatedness_links():
    outcome = lookups("vector").run("related_places", {"place_id": 101})

    assert outcome.status == "refused"
    assert outcome.reason == "쓸 수 없는 조회입니다."


def test_congestion_says_the_grade_in_korean_and_brings_its_policy_page():
    subject = lookups()

    outcome = subject.run("congestion", {"place_id": 101, "date": "2026-10-17"})

    passage = next(
        p for p in subject.fetched.passages if p.id == "hanjeok:congestion/101@2026-10-17"
    )
    assert outcome.status == "ok"
    assert outcome.summary == "10월 17일 예보: 매우혼잡 (상위 8%)"
    assert "매우혼잡" in passage.text and "VERY_CROWDED" not in passage.text
    assert "10월 20일(2026-10-20) 보통" in passage.text
    assert outcome.produced == (
        "hanjeok:congestion/101@2026-10-17",
        "wiki:concepts/congestion-diagnosis.md",
    )
    assert outcome.as_of == "2026-10-13T14:20:05Z", (
        "the time Hanjeok was asked, not the export time"
    )


def test_a_place_without_coverage_is_no_data_and_is_never_called_quiet():
    subject = lookups(known=(150,))

    outcome = subject.run("congestion", {"place_id": 150, "date": "2026-10-17"})

    passage = subject.fetched.passages[-1]
    assert outcome.status == "no_data"
    assert outcome.produced == ("hanjeok:congestion/150@2026-10-17",)
    assert "한적하다는 뜻이 아니다" in passage.text
    assert not any(grade in passage.text for grade in ("여유", "보통", "매우혼잡"))


@pytest.mark.parametrize(
    ("day", "why"),
    [
        (None, "필요"),
        ("토요일", "YYYY-MM-DD"),
        ("2026-10-12", "부터"),
        ("2026-11-12", "까지만"),
        ("2026-13-01", "YYYY-MM-DD"),
    ],
)
def test_congestion_refuses_a_missing_malformed_or_out_of_window_date(day, why):
    outcome = lookups().run("congestion", {"place_id": 101, "date": day})

    assert outcome.status == "refused"
    assert why in outcome.reason


def test_alternatives_come_numbered_in_hanjeoks_order_with_both_policy_pages():
    subject = lookups()

    outcome = subject.run("alternatives", {"place_id": 101, "date": "2026-10-17"})

    passage = next(
        p for p in subject.fetched.passages if p.id == "hanjeok:alternatives/101@2026-10-17"
    )
    assert [line.split(" — ")[0] for line in passage.text.splitlines()[1:]] == [
        "1. 솔내 한옥마을",
        "2. 물빛 서원",
        "3. 달맞이 숲길",
    ]
    assert "바꿀 수 없다" in passage.text
    assert {
        "wiki:concepts/alternative-scoring.md",
        "wiki:decisions/keep-llm-out-of-ranking.md",
    } <= set(outcome.produced)
    ranked = [(e["to"], e["rank"]) for e in subject.fetched.edges if e["kind"] == "alternative"]
    assert ranked == [("hanjeok:place/118", 1), ("hanjeok:place/124", 2), ("hanjeok:place/131", 3)]


def test_no_alternatives_is_no_data_with_something_to_cite():
    subject = lookups(known=(118,))

    outcome = subject.run("alternatives", {"place_id": 118, "date": "2026-10-17"})

    assert outcome.status == "no_data"
    assert outcome.produced == ("hanjeok:alternatives/118@2026-10-17",)


def test_hanjeok_being_unreachable_fails_the_step_and_adds_nothing_citable():
    class Down(LiveClient):
        def __init__(self) -> None:
            pass

        def congestion(self, place_id, day):
            raise LiveError("service_unreachable")

    subject = lookups(live=Down())
    before = dict(subject.fetched.labels)

    outcome = subject.run("congestion", {"place_id": 101, "date": "2026-10-17"})

    assert (outcome.status, outcome.cause) == ("failed", "service_unreachable")
    assert subject.fetched.labels == before


def test_one_question_asks_hanjeok_once_for_the_same_thing():
    calls = []
    real = replay_live()

    class Counting(LiveClient):
        def __init__(self) -> None:
            pass

        def congestion(self, place_id, day):
            calls.append((place_id, day))
            return real.congestion(place_id, day)

    subject = lookups(live=Counting())
    subject.run("congestion", {"place_id": 101, "date": "2026-10-17"})
    repeat = subject.run("congestion", {"place_id": 101, "date": "2026-10-17"})

    assert calls == [(101, "2026-10-17")]
    assert repeat.status == "refused" and "이미" in repeat.reason


def test_events_at_a_place_on_a_day():
    subject = lookups()

    during = subject.run("events", {"place_id": 101, "date": "2026-10-17"})
    after = subject.run("events", {"place_id": 101, "date": "2026-10-26"})

    assert during.status == "ok" and "가람궁 달빛 야행" in during.summary
    assert during.produced == ("hanjeok:events/101@2026-10-17",)
    assert after.status == "no_data" and after.produced == ("hanjeok:events/101@2026-10-26",)
    assert {
        "from": "festival:garam-night",
        "to": "hanjeok:place/101",
        "kind": "held_at",
        "rank": None,
    } in subject.fetched.edges


def test_policy_returns_wiki_pages_as_policy_citations():
    subject = lookups(known=())

    outcome = subject.run("policy", {"text": "대안은 어떤 기준으로 골라?"})

    assert outcome.status == "ok"
    assert len(outcome.produced) == 3 and all(p.startswith("wiki:") for p in outcome.produced)
    assert subject.run("policy", {"text": "가" * 201}).status == "refused"


def test_a_lookup_still_works_when_the_wiki_is_not_loaded():
    subject = lookups(policy=FakePolicy({}))

    outcome = subject.run("congestion", {"place_id": 101, "date": "2026-10-17"})

    assert outcome.status == "ok"
    assert outcome.produced == ("hanjeok:congestion/101@2026-10-17",)


def test_an_action_that_is_not_a_lookup_is_refused():
    assert lookups().run("drop_database", {}).status == "refused"
    assert lookups().run("_declare", {}).status == "refused"


def test_a_policy_question_gets_the_page_its_words_name_before_anything_search_finds():
    class Unhelpful(FakePolicy):
        """Search returns nothing useful, as it did for a Korean question over
        the English wiki."""

        def search(self, text, *, limit):
            return []

    subject = lookups(known=(), policy=Unhelpful())

    grades = subject.run("policy", {"text": "혼잡 등급은 어떻게 나눠?"})
    order = subject.run("policy", {"text": "대안 장소는 어떤 기준으로 순서를 정해?"})

    assert grades.produced == ("wiki:concepts/congestion-diagnosis.md",)
    assert order.produced == (
        "wiki:concepts/alternative-scoring.md",
        "wiki:decisions/keep-llm-out-of-ranking.md",
    )
    assert subject.run("policy", {"text": "그 밖의 것"}).status == "no_data"
