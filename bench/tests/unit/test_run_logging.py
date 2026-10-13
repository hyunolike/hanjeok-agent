import json
import logging

from tests.unit.test_evaluation import Runtime

from bench.eval.runner import PairRunner


def test_arm_log_is_structured_and_does_not_contain_prompt_text(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="bench.runs")
    PairRunner(Runtime(), tmp_path / "runs.jsonl").pair(
        question_id="q", question="private-question-body", corpus="third"
    )
    messages = [r.message for r in caplog.records if r.name == "bench.runs"]
    assert len(messages) == 2
    rows = [json.loads(message) for message in messages]
    assert all(row["event"] == "bench.run" and row["supplied_passages"] >= 1 for row in rows)
    assert rows[0]["expanded_passages"] == 0
    assert all(row["outcome"] == "answered" and row["repair_count"] == 0 for row in rows)
    assert "private-question-body" not in "".join(messages)
    assert "Alpha fact" not in "".join(messages)
