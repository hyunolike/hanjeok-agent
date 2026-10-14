"""Streams the service produces, kept as files the frontend's tests also read.

One shape, checked from both sides: here the service must still produce these
files, and `frontend/src/lib/guide-contract.test.ts` must still parse them. A
change to an event's fields fails one of the two until both agree.

    GUIDE_RECORD_STREAMS=1 uv run pytest tests/contract/test_guide_recorded_streams.py

rewrites the files after an intended change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.contract.test_guide_api_contract import TestRuntime, frames
from tests.guide_fakes import action, answer, model_down

from guide.api import create_app

DIRECTORY = Path(__file__).parents[1] / "fixtures" / "guide-streams"

CASES = {
    "answered": (
        "이번 토요일 가람궁 대신 조용한 곳 있어?",
        (
            action("congestion", place_id=101, date="2026-10-17"),
            action("alternatives", place_id=101, date="2026-10-17"),
            answer(
                "10월 17일 가람궁은 매우혼잡 예보입니다. 한적이 정한 순서로 솔내 한옥마을, 물빛 서원, 달맞이 숲길이 대안입니다.",
                "hanjeok:congestion/101@2026-10-17",
                "hanjeok:alternatives/101@2026-10-17",
                "wiki:concepts/alternative-scoring.md",
            ),
        ),
    ),
    "no-data": (
        "새벽 등대는 이번 토요일에 한적해?",
        (
            action("congestion", place_id=150, date="2026-10-17"),
            answer(
                "새벽 등대는 한적이 혼잡을 예보하지 않는 곳이라 알 수 없습니다.",
                "hanjeok:congestion/150@2026-10-17",
            ),
        ),
    ),
    "refused-step": (
        "가람궁은 토요일에 얼마나 붐벼?",
        (
            action("congestion", place_id=124, date="2026-10-17"),
            action("congestion", place_id=101, date="2026-10-17"),
            answer("10월 17일 가람궁은 매우혼잡 예보입니다.", "hanjeok:congestion/101@2026-10-17"),
        ),
    ),
    "ambiguous": ("은행나무길은 토요일에 붐벼?", ()),
    "declined": ("가람궁 입장료는 얼마야?", ()),
    "failed": ("이번 토요일 가람궁 어때?", (model_down(),)),
}


def record(name: str) -> list[dict]:
    question, script = CASES[name]
    http = TestClient(create_app(TestRuntime(*script), origins=[]))
    events = frames(http.post("/guide/ask", json={"question": question}))
    out = []
    for event, data in events:
        # The three values that differ on every run.
        if event == "visit":
            data["visit_id"] = "recorded-visit"
        if event == "done":
            data["elapsed_ms"], data["generated_at"] = 0, "2026-10-13T14:20:30Z"
        out.append({"event": event, "data": data})
    return out


@pytest.mark.parametrize("name", list(CASES))
def test_the_service_still_produces_the_recorded_stream(name):
    path = DIRECTORY / f"{name}.json"
    produced = record(name)
    if os.environ.get("GUIDE_RECORD_STREAMS") == "1":
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(produced, ensure_ascii=False, indent=1) + "\n", "utf-8")

    assert json.loads(path.read_text("utf-8")) == produced
