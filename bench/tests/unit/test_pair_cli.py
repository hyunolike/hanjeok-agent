import json

from test_pair_validity import FixtureRuntime


def test_pair_cli_shows_two_answers_input_diff_and_committable_records(tmp_path, capsys):
    from bench.cli import main

    status = main(
        [
            "pair",
            "--question-id",
            "q1",
            "--question",
            "What?",
            "--corpus",
            "third",
            "--show-diff",
            "--runs-file",
            str(tmp_path / "runs.jsonl"),
        ],
        runtime=FixtureRuntime(),
    )
    assert status == 0
    body = json.loads(capsys.readouterr().out)
    assert body["valid"] and body["input_diff"]["shared_equal"]
    assert {r["strategy"] for r in body["runs"]} == {"whole", "graph"}
    assert all(r["answer"] == "fact" for r in body["runs"])
    assert body["input_diff"]["differences"] == ["supplied"]
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 2


def test_pair_cli_invalid_pair_has_nonzero_exit_but_keeps_both_records(tmp_path, capsys):
    from bench.cli import main

    status = main(
        [
            "pair",
            "--question-id",
            "q1",
            "--question",
            "What?",
            "--corpus",
            "third",
            "--runs-file",
            str(tmp_path / "runs.jsonl"),
        ],
        runtime=FixtureRuntime(revisions=("old", "new")),
    )
    assert status == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 2


def test_pair_cli_rejects_blank_id_before_runtime_or_output_file(tmp_path, capsys):
    from bench.cli import main

    runtime = FixtureRuntime()
    status = main(
        [
            "pair",
            "--question-id",
            " ",
            "--question",
            "What?",
            "--corpus",
            "third",
            "--runs-file",
            str(tmp_path / "runs.jsonl"),
        ],
        runtime=runtime,
    )
    assert status == 2
    assert runtime.requests == [] and not (tmp_path / "runs.jsonl").exists()
    assert "invalid request" in json.loads(capsys.readouterr().out)["cause"]
