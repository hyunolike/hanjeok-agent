from __future__ import annotations

import json
from datetime import UTC, date, datetime

import httpx
import pytest
from tests.guide_fakes import FIXTURES, replay_live

from guide.live import LiveClient, LiveError, Recording


def test_a_covered_place_has_a_grade_and_the_better_dates_in_hanjeoks_order():
    result = replay_live().congestion(101, "2026-10-17")

    assert result.has_data
    assert (result.grade, result.percentile) == ("VERY_CROWDED", 92.0)
    assert [d.date for d in result.better_dates] == ["2026-10-20", "2026-10-21"]
    assert result.fetched_at == "2026-10-13T14:20:05Z"


def test_an_uncovered_place_is_its_own_outcome_and_has_no_grade():
    result = replay_live().congestion(150, "2026-10-17")

    assert result.has_data is False
    assert result.grade is None and result.concentration is None


def test_alternatives_keep_hanjeoks_order():
    result = replay_live().alternatives(101, "2026-10-17")

    assert [item.name for item in result.items] == ["솔내 한옥마을", "물빛 서원", "달맞이 숲길"]
    # Not sorted by concentration, distance or anything else on the way in.
    assert [item.concentration for item in result.items] == [49.0, 28.0, 22.0]


def test_fields_the_guide_does_not_use_are_not_carried():
    result = replay_live().congestion(101, "2026-10-17")
    raw = json.loads(
        (FIXTURES / "hanjeok-live" / "congestion-101-2026-10-17.json").read_text("utf-8")
    )

    assert "feltCongestion" in raw["body"]["data"], "the recording has it"
    carried = json.dumps(
        [getattr(result, name) for name in result.__dataclass_fields__], default=str
    )
    assert "img.invalid" not in carried
    assert not {"felt", "image", "message"} & {
        name.split("_")[0] for name in result.__dataclass_fields__
    }


def test_a_place_hanjeok_does_not_have():
    with pytest.raises(LiveError) as caught:
        replay_live().congestion(99999, "2026-10-17")
    assert caught.value.cause == "unknown_place"


def test_replay_never_reaches_the_network_and_a_missing_recording_is_not_no_data():
    with pytest.raises(LiveError) as caught:
        replay_live().congestion(101, "2026-10-30")
    assert caught.value.cause == "service_unreachable"


def test_replay_uses_the_day_the_recording_was_made():
    assert replay_live().today() == date(2026, 10, 13)


def client(handler, **kwargs) -> LiveClient:
    return LiveClient(
        base_url="https://hanjeok.test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: datetime(2026, 10, 13, 15, 30, tzinfo=UTC),
        **kwargs,
    )


def test_live_calls_exactly_the_congestion_path_with_the_date():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, dict(request.url.params)))
        return httpx.Response(
            200,
            json=json.loads(
                (FIXTURES / "hanjeok-live" / "congestion-101-2026-10-17.json").read_text("utf-8")
            )["body"],
        )

    result = client(handler).congestion(101, "2026-10-17")

    assert seen == [("GET", "/api/v1/attractions/101/congestion", {"date": "2026-10-17"})]
    assert result.grade == "VERY_CROWDED"
    assert result.fetched_at == "2026-10-13T15:30:00Z"


def test_the_client_has_no_way_to_call_the_detail_endpoint():
    # That endpoint records a view on every call. The guide must never write to Hanjeok.
    public = {name for name in dir(LiveClient) if not name.startswith("_")}
    assert public == {"congestion", "alternatives", "today"}


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            500, json={"success": False, "data": None, "error": {"code": "X", "message": "y"}}
        ),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json={"success": True, "data": {"hasCongestionData": True}}),
        httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "hasCongestionData": True,
                    "attraction": {"name": "가람궁"},
                    "diagnosis": {"grade": "QUIET", "concentration": 1, "percentile": 1},
                },
            },
        ),
    ],
    ids=["server error", "not json", "missing fields", "a grade Hanjeok does not define"],
)
def test_anything_but_the_documented_shape_is_unreachable_not_a_guess(response):
    with pytest.raises(LiveError) as caught:
        client(lambda request: response).congestion(101, "2026-10-17")
    assert caught.value.cause == "service_unreachable"


def test_a_timeout_is_unreachable():
    def handler(request):
        raise httpx.ConnectTimeout("slow")

    with pytest.raises(LiveError) as caught:
        client(handler).alternatives(101, "2026-10-17")
    assert caught.value.cause == "service_unreachable"


def test_record_then_replay_gives_the_same_answer(tmp_path):
    body = json.loads(
        (FIXTURES / "hanjeok-live" / "alternatives-101-2026-10-17.json").read_text("utf-8")
    )["body"]
    recording = Recording(tmp_path / "rec")

    recorded = client(
        lambda request: httpx.Response(200, json=body), mode="record", recording=recording
    ).alternatives(101, "2026-10-17")
    replayed = LiveClient(mode="replay", recording=recording).alternatives(101, "2026-10-17")

    assert replayed == recorded
    assert recording.today() == date(2026, 10, 14), "15:30 UTC is already the 14th in Seoul"


@pytest.mark.parametrize(
    ("kwargs"),
    [{"mode": "replay"}, {"mode": "record", "base_url": "x"}, {"mode": "live"}, {"mode": "other"}],
)
def test_a_mode_without_what_it_needs_fails_at_construction(kwargs):
    with pytest.raises(ValueError):
        LiveClient(**kwargs)
