from __future__ import annotations

import json
from pathlib import Path

from guide.cli import main
from guide.graph.refresh import RefreshError, RefreshResult

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_refresh_prints_counts_and_the_generation(capsys):
    def run(export, cache):
        return RefreshResult(
            "hanjeok", "gen-1", export.counts, export.exported_at, export.sha256, 40, 0
        )

    status = main(["refresh", "--export", str(FIXTURES / "hanjeok-export")], run_refresh=run)

    out = json.loads(capsys.readouterr().out)
    assert status == 0
    assert out["generation"] == "gen-1"
    assert out["counts"] == {"places": 41, "related": 55, "events": 5, "regions": 2}


def test_a_broken_export_exits_non_zero_names_the_file_and_never_starts_a_refresh(capsys):
    started = []

    status = main(
        ["refresh", "--export", str(FIXTURES / "hanjeok-export-broken")],
        run_refresh=lambda export, cache: started.append(export),
    )

    err = json.loads(capsys.readouterr().err)
    assert status == 1
    assert started == []
    assert err["cause"] == "hash_mismatch"
    assert "related.jsonl" in err["detail"]
    assert err["active_copy"] == "unchanged"


def test_a_refresh_that_fails_reports_its_cause(capsys):
    def run(export, cache):
        raise RefreshError("count_mismatch", "export has 40, graph has 39")

    status = main(["refresh", "--export", str(FIXTURES / "hanjeok-export")], run_refresh=run)

    assert status == 1
    assert json.loads(capsys.readouterr().err)["cause"] == "count_mismatch"


def test_check_verifies_without_refreshing(capsys):
    started = []

    status = main(
        ["refresh", "--export", str(FIXTURES / "hanjeok-export"), "--check"],
        run_refresh=lambda export, cache: started.append(export),
    )

    assert status == 0
    assert started == []
    assert json.loads(capsys.readouterr().out)["counts"]["places"] == 41


def test_rescore_is_a_command_and_reports_a_missing_run(capsys):
    # The subcommand was once wired into `main` but never added to the parser,
    # and the only test of it called the function underneath.
    seen = []

    def run(args):
        seen.append(args.report)
        raise FileNotFoundError(args.report)

    status = main(["rescore", "--report", "r1"], run_rescore=run)

    assert seen == ["r1"]
    assert status == 1
    assert json.loads(capsys.readouterr().err)["cause"] == "no_report"


def test_every_command_the_parser_offers_is_handled():
    from guide.cli import parser

    choices = next(a for a in parser()._actions if a.dest == "command").choices
    assert set(choices) == {"refresh", "eval", "rescore", "publish", "mcp"}


def test_mcp_is_a_command_and_defaults_to_stdio():
    seen = []

    status = main(["mcp"], run_mcp=lambda args: seen.append(args.transport) or 0)

    assert (status, seen) == (0, ["stdio"])
