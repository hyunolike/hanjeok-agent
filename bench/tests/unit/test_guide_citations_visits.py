from __future__ import annotations

from guide import citations as cite
from guide.scope import Turn
from guide.visits import VISIT_TTL_S, WINDOW_S, Visits

FETCHED = {
    "hanjeok:place/101": "가람궁",
    "wiki:concepts/congestion-diagnosis.md": "Congestion Diagnosis",
}


def test_ids_say_which_kind_they_are():
    assert cite.kind_of(cite.wiki("concepts/a.md")) == "policy"
    for record in (
        cite.place(1),
        cite.related(1),
        cite.congestion(1, "2026-10-17"),
        cite.events(1, None),
    ):
        assert cite.kind_of(record) == "record"
    assert cite.congestion(101, "2026-10-17") == "hanjeok:congestion/101@2026-10-17"


def test_an_answer_citing_what_was_fetched_passes_and_duplicates_collapse():
    verdict = cite.gate("답", ["hanjeok:place/101", "hanjeok:place/101"], FETCHED)

    assert verdict.ok
    assert verdict.citations == ("hanjeok:place/101",)


def test_an_answer_with_no_citation_or_no_text_is_refused():
    assert not cite.gate("답", [], FETCHED).ok
    assert not cite.gate("   ", ["hanjeok:place/101"], FETCHED).ok


def test_a_citation_that_was_not_fetched_for_this_question_is_refused_without_being_repeated():
    invented = "hanjeok:place/999; DROP"
    verdict = cite.gate("답", ["hanjeok:place/101", invented], FETCHED)

    assert not verdict.ok
    assert invented not in verdict.reason
    assert "2개 중 1개" in verdict.reason


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_a_visit_keeps_what_was_asked_about_and_not_what_was_answered():
    visits = Visits()
    visit = visits.open(None)
    visits.remember(visit, Turn("가람궁 어때?", (101,), ("2026-10-17",)))

    assert visits.open(visit) == visit
    assert visits.turns(visit) == (Turn("가람궁 어때?", (101,), ("2026-10-17",)),)
    assert not hasattr(visits.turns(visit)[0], "answer")


def test_an_unknown_or_expired_visit_gets_a_new_id_rather_than_an_error():
    clock = Clock()
    visits = Visits(clock=clock)
    first = visits.open(None)
    clock.now += VISIT_TTL_S + 1

    second = visits.open(first)

    assert second != first
    assert visits.turns(second) == ()
    assert visits.open("made-up") not in ("made-up", first, second)


def test_ids_are_not_guessable_from_one_another():
    visits = Visits()
    ids = {visits.open(None) for _ in range(50)}
    assert len(ids) == 50 and all(len(i) >= 20 for i in ids)


def test_the_per_visitor_limit_says_when_to_come_back_and_then_lifts():
    clock = Clock()
    visits = Visits(per_visitor=2, clock=clock)
    visit = visits.open(None)

    assert visits.admit(visit, "1.1.1.1") is None
    clock.now += 60
    assert visits.admit(visit, "1.1.1.1") is None
    limit = visits.admit(visit, "1.1.1.1")

    assert limit.scope == "visitor"
    assert WINDOW_S - 120 < limit.retry_after_s <= WINDOW_S - 59
    clock.now += limit.retry_after_s
    assert visits.admit(visit, "1.1.1.1") is None


def test_a_new_tab_from_the_same_address_does_not_reset_the_limit():
    visits = Visits(per_visitor=1)
    assert visits.admit(visits.open(None), "1.1.1.1") is None

    assert visits.admit(visits.open(None), "1.1.1.1").scope == "visitor"
    assert visits.admit(visits.open(None), "2.2.2.2") is None


def test_the_daily_limit_is_for_everyone_and_a_refused_question_is_not_counted():
    visits = Visits(per_visitor=5, per_day=2)
    assert visits.admit(visits.open(None), "1.1.1.1") is None
    assert visits.admit(visits.open(None), "2.2.2.2") is None

    assert visits.admit(visits.open(None), "3.3.3.3").scope == "day"
    assert visits.admit(visits.open(None), "3.3.3.3").scope == "day"


def test_a_choice_must_be_one_the_visit_was_offered():
    visits = Visits()
    visit, other = visits.open(None), visits.open(None)
    visits.offer(visit, [140, 141])

    assert visits.was_offered(visit, 141)
    assert not visits.was_offered(visit, 101)
    assert not visits.was_offered(other, 141)
