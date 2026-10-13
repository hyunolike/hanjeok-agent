from __future__ import annotations

import pytest

from guide.model import RATE_LIMIT_WAITS_S, GuideModel, ModelFailure


def model(*outcomes):
    subject = GuideModel(settings={"name": "x", "temperature": 0, "max_tokens": 10})
    waits: list[float] = []
    queue = list(outcomes)

    def once(system, user, schema, *, timeout):
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    subject._decide_once = once
    subject._sleep = waits.append
    return subject, waits


def test_a_rate_limit_is_waited_out_and_tried_again():
    failures = [ModelFailure("rate_limit")] * len(RATE_LIMIT_WAITS_S)
    subject, waits = model(*failures, {"action": "answer"})

    assert subject.decide("s", "u", {}, timeout=60) == {"action": "answer"}
    assert tuple(waits) == RATE_LIMIT_WAITS_S


def test_it_gives_up_after_the_listed_waits():
    subject, waits = model(*[ModelFailure("rate_limit")] * 4)

    with pytest.raises(ModelFailure, match="rate_limit"):
        subject.decide("s", "u", {}, timeout=60)
    assert len(waits) == len(RATE_LIMIT_WAITS_S)


def test_other_failures_are_not_retried():
    subject, waits = model(ModelFailure("authentication"), {"action": "answer"})

    with pytest.raises(ModelFailure, match="authentication"):
        subject.decide("s", "u", {}, timeout=60)
    assert waits == []


def test_it_does_not_wait_past_the_questions_deadline():
    subject, waits = model(ModelFailure("rate_limit"), {"action": "answer"})

    with pytest.raises(ModelFailure):
        subject.decide("s", "u", {}, timeout=6)
    assert waits == []


def test_without_a_key_the_failure_is_configuration_and_names_no_secret():
    with pytest.raises(ModelFailure, match="configuration"):
        GuideModel().decide("s", "u", {}, timeout=5)
