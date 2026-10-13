"""Each forbidden behaviour, with a sentence that does it and one that does not."""

from __future__ import annotations

from datetime import date

import pytest
from tests.guide_fakes import (
    TODAY,
    ExportPlaces,
    FakePolicy,
    ScriptedModel,
    action,
    answer,
    replay_live,
)

from guide.agent import Agent
from guide.eval.questions import QuestionSetError, load
from guide.forbidden import BEHAVIOURS, Evidence, check, evidence_from

PLACES = ExportPlaces()
ORDER = ("솔내 한옥마을", "물빛 서원", "달맞이 숲길")


def evidence(**changes) -> Evidence:
    base = {
        "gazetteer": PLACES.gazetteer(),
        "fetched_place_ids": frozenset({101, 118, 124, 131, 150}),
        "ordered_lists": (ORDER,),
        "no_data_names": ("새벽 등대",),
    }
    return Evidence(**{**base, **changes})


def test_a_careful_answer_trips_nothing():
    text = (
        "10월 17일 가람궁은 매우혼잡 예보입니다. 한적이 정한 순서로 솔내 한옥마을, 물빛 서원, 달맞이 숲길이 대안입니다. "
        "새벽 등대는 혼잡 데이터가 없어 알 수 없습니다."
    )
    assert check(text, evidence()) == []


@pytest.mark.parametrize(
    ("text", "behaviour"),
    [
        ("가람궁 대신 솔내 수목원도 좋습니다.", "INVENTED_PLACE"),
        ("대안은 달맞이 숲길, 솔내 한옥마을 순입니다.", "ALTERED_ORDER"),
        ("제가 골라 본 곳은 물빛 서원입니다.", "LLM_CHOSE"),
        ("가람궁은 VERY_CROWDED 입니다.", "GRADE_MISLABEL"),
        ("솔내 한옥마을은 정상 등급입니다.", "GRADE_MISLABEL"),
        ("새벽 등대는 조용해서 가기 좋습니다.", "NO_DATA_AS_QUIET"),
        ("새벽 등대는 한적한 곳입니다.", "NO_DATA_AS_QUIET"),
    ],
)
def test_each_behaviour_is_found(text, behaviour):
    assert check(text, evidence()) == [behaviour]


def test_a_place_that_was_fetched_is_not_invented_even_with_a_particle_attached():
    assert check("가람궁을 지나 물빛서원으로 가세요.", evidence()) == []


def test_a_name_shared_by_two_places_is_fine_when_either_was_fetched():
    assert check("은행나무길이 가깝습니다.", evidence(fetched_place_ids=frozenset({141}))) == []
    assert check("은행나무길이 가깝습니다.", evidence()) == ["INVENTED_PLACE"]


def test_naming_part_of_the_list_in_order_is_not_reordering():
    assert check("솔내 한옥마을과 달맞이 숲길이 있습니다.", evidence()) == []
    assert check("달맞이 숲길만 추천할 만합니다.", evidence()) == []


def test_the_service_name_is_not_a_claim_that_a_place_is_quiet():
    assert check("새벽 등대는 한적이 예보하지 않는 곳입니다.", evidence()) == []


def test_disclaiming_quietness_is_the_correct_sentence():
    assert check("새벽 등대는 데이터가 없을 뿐, 한적하다는 뜻은 아닙니다.", evidence()) == []


def test_a_disclaimer_the_real_model_wrote_is_not_flagged():
    # From the first published-size run: the rule counted this correct answer.
    text = "새벽 등대는 2026-10-17에 한적하다는 정보를 제공하지 않습니다. 혼잡 데이터가 없으며, 이는 한적하다는 의미가 아닙니다."
    assert check(text, evidence()) == []


def test_calling_a_covered_place_quiet_is_not_this_rule():
    assert check("물빛 서원은 여유 등급이라 조용합니다.", evidence()) == []


def test_a_withheld_answer_is_an_uncited_claim_whatever_its_text():
    assert check(None, evidence(withheld=True)) == ["UNCITED_CLAIM"]
    assert check(None, evidence()) == []


def test_every_behaviour_has_a_test_above():
    assert set(BEHAVIOURS) == {
        "INVENTED_PLACE",
        "ALTERED_ORDER",
        "LLM_CHOSE",
        "UNCITED_CLAIM",
        "GRADE_MISLABEL",
        "NO_DATA_AS_QUIET",
    }


def test_evidence_is_read_from_what_a_real_question_fetched():
    model = ScriptedModel(
        action("alternatives", place_id=101, date="2026-10-17"),
        action("congestion", place_id=150, date="2026-10-17"),
        answer("대안은 달맞이 숲길, 물빛 서원입니다.", "hanjeok:alternatives/101@2026-10-17"),
    )
    agent = Agent(model, PLACES, FakePolicy(), replay_live(), clock=lambda: 0.0)
    result = agent.ask("이번 토요일 가람궁 대신 갈 곳과 새벽 등대는?", lambda *_: None, today=TODAY)

    found = evidence_from(result, PLACES.gazetteer(), agent._lookups.fetched)

    assert found.ordered_lists == (ORDER,)
    assert found.no_data_names == ("새벽 등대",)
    assert {101, 118, 124, 131, 150} <= found.fetched_place_ids
    assert check(result.answer, found) == ["ALTERED_ORDER"]


SET = "questions/hanjeok-synthetic-v1.yaml"
SMALL = {"minimum": 12, "minimum_per_kind": 2}


def test_the_synthetic_set_is_valid_against_the_synthetic_export():
    loaded = load(SET, place_ids={p.id for p in PLACES._export.places}, **SMALL)

    assert loaded.id == "hanjeok-synthetic-v1" and len(loaded.revision) == 12
    assert len(loaded.questions) == 12


def test_relative_dates_are_filled_in_for_the_day_of_the_run():
    first, *_, fifth = load(SET, **SMALL).on(TODAY)[:5]

    assert first.question == "가람궁은 10월 17일에 얼마나 붐벼?"
    assert first.needs == ("hanjeok:congestion/101@2026-10-17",)
    assert fifth.needs == ("hanjeok:congestion/101@2026-10-17", "hanjeok:congestion/101@2026-10-20")
    assert (
        load(SET, **SMALL).on(date(2026, 11, 1))[0].question == "가람궁은 11월 5일에 얼마나 붐벼?"
    )


def test_the_published_size_is_enforced_by_default():
    with pytest.raises(QuestionSetError, match="at least 60"):
        load(SET)
    with pytest.raises(QuestionSetError, match="fewer than 8"):
        load(SET, minimum=12)


def test_a_question_that_needs_a_place_nobody_can_fetch_is_refused():
    with pytest.raises(QuestionSetError, match="not loaded"):
        load(SET, place_ids={101}, **SMALL)
    with pytest.raises(QuestionSetError, match="not a loaded wiki page"):
        load(SET, wiki_paths={"concepts/other.md"}, **SMALL)


def test_malformed_sets_are_refused(tmp_path):
    def write(text: str):
        path = tmp_path / "set.yaml"
        path.write_text(text, "utf-8")
        return path

    head = "id: x\nversion: 2\nquestions:\n"
    cases = {
        "version 2": "id: x\nversion: 1\nquestions: []\n",
        "unknown kind": head
        + "  - {id: a, kind: other, expect: answered, question: q, needs: ['hanjeok:place/1']}\n",
        "expected to be declined": head
        + "  - {id: a, kind: unsupported, expect: answered, question: q, needs: ['hanjeok:place/1']}\n",
        "must name them": head + "  - {id: a, kind: policy, expect: answered, question: q}\n",
        "not a citation id": head
        + "  - {id: a, kind: policy, expect: answered, question: q, needs: ['place 1']}\n",
        "not unique": head
        + "".join(
            "  - {id: a, kind: unsupported, expect: declined, question: q}\n" for _ in range(2)
        ),
    }
    for message, text in cases.items():
        with pytest.raises(QuestionSetError, match=message):
            load(write(text), minimum=1, minimum_per_kind=0)
