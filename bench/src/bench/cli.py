"""Callable local interface. JSON output is suitable for later run recording."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from bench.api import AskRequest
from bench.eval.runner import PairRunner
from bench.eval.service import DEFAULT_ROOT, EvaluationService, ReportStore
from bench.runtime import BenchError, runtime_from_env


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="bench")
    commands = root.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="answer one question using supplied evidence")
    ask.add_argument("--question", required=True)
    ask.add_argument("--corpus", required=True)
    ask.add_argument("--strategy", required=True, choices=("graph", "whole"))
    ask.add_argument("--show-supplied", action="store_true")
    pair = commands.add_parser("pair", help="record and compare both arms under shared inputs")
    pair.add_argument("--question-id", required=True)
    pair.add_argument("--question", required=True)
    pair.add_argument("--corpus", required=True)
    pair.add_argument("--show-diff", action="store_true")
    pair.add_argument(
        "--runs-file", type=Path, default=Path("runs") / f"pairs-{datetime.now(UTC).date()}.jsonl"
    )
    corpus = commands.add_parser("corpus", help="manage disposable derived state")
    operations = corpus.add_subparsers(dest="operation", required=True)
    for operation in ("load", "rebuild"):
        operations.add_parser(operation).add_argument("name")
    operations.add_parser("list")
    run = commands.add_parser("run", help="evaluate a stored question set across both strategies")
    run.add_argument("--question-set", required=True)
    run.add_argument("--corpus", required=True)
    report = commands.add_parser(
        "report", help="read a durable report without database or API keys"
    )
    report.add_argument("--id", required=True)
    report.add_argument("--reports-root", type=Path, default=DEFAULT_ROOT / "reports")
    return root


def main(argv=None, *, runtime=None, evaluation=None) -> int:
    args = parser().parse_args(argv)
    owned = runtime is None and args.command != "report"
    owned_evaluation = False
    status = 0
    try:
        # Validate before constructing anything that can reach a service.
        if args.command in ("ask", "pair"):
            AskRequest(
                question=args.question,
                corpus=args.corpus,
                strategy=args.strategy if args.command == "ask" else "whole",
            )
        if args.command == "pair" and (not args.question_id.strip() or len(args.question_id) > 100):
            print(json.dumps({"outcome": "load_failed", "cause": "invalid request fields"}))
            return 2
        if owned:
            runtime = runtime_from_env()
        if args.command == "report":
            body = ReportStore(args.reports_root).get(args.id)
            if body["status"] != "completed":
                status = 1
        elif args.command == "run":
            if evaluation is None:
                evaluation = EvaluationService(runtime)
                owned_evaluation = True
            body = evaluation.run(args.question_set, args.corpus)
        elif args.command == "ask":
            result = runtime.ask(args.question, args.corpus, args.strategy)
            if result.outcome in ("answered", "no_grounds"):
                body = result.to_dict(show_supplied=args.show_supplied)
            else:
                body = {"outcome": result.outcome, "cause": result.cause}
                status = 1
        elif args.command == "pair":
            result = PairRunner(runtime, args.runs_file).pair(
                question_id=args.question_id, question=args.question, corpus=args.corpus
            )
            body = result.to_dict(show_diff=args.show_diff)
            status = 0 if result.scoring_runs else 1
        elif args.operation == "list":
            body = runtime.list_corpora()
        else:
            body = runtime.rebuild(args.name)
    except ValidationError:
        body, status = {"outcome": "load_failed", "cause": "invalid request fields"}, 2
    except BenchError as error:
        body, status = {"outcome": error.outcome, "cause": error.cause}, 1
    except Exception:
        body, status = {"outcome": "load_failed", "cause": "local runtime unavailable"}, 1
    finally:
        if owned_evaluation:
            evaluation.close()
        if owned and runtime is not None:
            runtime.close()
    print(json.dumps(body, ensure_ascii=False, default=str))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
