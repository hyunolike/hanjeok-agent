"""`guide` — the commands that are run by hand, not over HTTP.

Refresh rebuilds the graph and evaluation spends model quota. A public endpoint
for either would need authentication this demo does not have, so they live
here (contracts/guide-api.md, "Not exposed").
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from guide.eval.questions import QuestionSetError
from guide.export import ExportError, read_export
from guide.graph.refresh import RefreshError

DEFAULT_CACHE = Path(".cache") / "guide-embeddings.sqlite"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="guide")
    commands = root.add_subparsers(dest="command", required=True)
    refresh = commands.add_parser(
        "refresh", help="replace the graph's copy of Hanjeok's data from an export"
    )
    refresh.add_argument(
        "--export", required=True, type=Path, help="directory holding manifest.json"
    )
    refresh.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="embedding cache file")
    refresh.add_argument(
        "--check", action="store_true", help="verify the export and stop; touch nothing"
    )
    refresh.add_argument(
        "--embed-only",
        action="store_true",
        help="fill the embedding cache and stop; needs the model but no database",
    )
    evaluate = commands.add_parser(
        "eval", help="run a question set under both strategies and store a report"
    )
    evaluate.add_argument("--question-set", required=True, type=Path)
    live = evaluate.add_mutually_exclusive_group()
    live.add_argument(
        "--record-live",
        action="store_true",
        help="call Hanjeok and keep the responses with the run",
    )
    live.add_argument(
        "--live-recording", type=Path, help="answer from this recording instead of calling Hanjeok"
    )
    evaluate.add_argument(
        "--no-judge", action="store_true", help="skip the judged metrics; costs far fewer calls"
    )
    evaluate.add_argument(
        "--allow-small", action="store_true", help="accept a set below the published size"
    )
    rescore = commands.add_parser(
        "rescore", help="judge the answers of a stored run without asking again"
    )
    rescore.add_argument("--report", required=True)
    mcp = commands.add_parser("mcp", help="serve the guide's tools over the Model Context Protocol")
    mcp.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    publish = commands.add_parser(
        "publish", help="make a stored report the one the evaluation page shows"
    )
    publish.add_argument("--report", required=True)
    return root


def _eval_from_env(args) -> dict:
    """The real evaluation. Spends model quota; never run in CI."""
    import os

    from bench.embeddings import LocalEmbedder
    from bench.graph.query import document_paths
    from bench.graph.store import driver_from_env
    from guide.eval.service import evaluate
    from guide.eval.store import ReportStore
    from guide.graph import read
    from guide.live import LiveClient, Recording
    from guide.model import GuideModel
    from guide.sources import WIKI_CORPUS, GraphPlaces, GraphPolicy

    driver = driver_from_env()
    try:
        active = read.active(driver)
        if active is None:
            raise RefreshError("not_ready", "no data is loaded; run `guide refresh` first")
        embedder = LocalEmbedder()
        if args.record_live:
            stamp = Path("runs") / "guide-live" / active.generation[:8]
            live = LiveClient(
                mode="record",
                base_url=os.environ.get("HANJEOK_BASE_URL", ""),
                recording=Recording(stamp),
            )
        else:
            directory = args.live_recording or Path("tests") / "fixtures" / "hanjeok-live"
            live = LiveClient(mode="replay", recording=Recording(directory))
        judge = None
        if not args.no_judge:
            from guide.eval.judge import patient_judge

            judge, _ = patient_judge(embedder)
        return evaluate(
            args.question_set,
            # The patient wrapper does the waiting, outside the question's clock.
            model=GuideModel(rate_limit_waits=()),
            patient=True,
            places=GraphPlaces(driver, active, embedder),
            policy=GraphPolicy(driver, embedder),
            live=live,
            judge=judge,
            store=ReportStore(),
            runs_dir=Path("runs"),
            generation=active.generation,
            export_sha256=active.export_sha256,
            export_as_of=active.exported_at,
            export_source=active.source,
            wiki_paths=document_paths(driver, WIKI_CORPUS) or None,
            allow_small=args.allow_small,
        )
    finally:
        driver.close()


def _rescore_from_env(args) -> dict:
    """Judging only. Spends judge quota; the answers are read from disk."""
    from bench.embeddings import LocalEmbedder
    from guide.eval.judge import patient_judge
    from guide.eval.service import rescore
    from guide.eval.store import ReportStore

    judge, transport = patient_judge(LocalEmbedder())
    return rescore(
        args.report,
        judge=judge,
        store=ReportStore(),
        runs_dir=Path("runs"),
        judge_waits=lambda: transport.waited,
    )


def _mcp_from_env(args) -> int:
    """Serve until the client goes away. Over stdio, standard output belongs to
    the protocol, so nothing here prints."""
    from guide.api import EnvRuntime
    from guide.mcp_server import build_server

    runtime = EnvRuntime()
    try:
        build_server(runtime).run(transport=args.transport)
    finally:
        runtime.close()
    return 0


def _embed_from_env(export, cache: Path) -> dict:
    """Compute embeddings into the cache file and nothing else.

    A container image is built where there is no database. Doing the slow part
    here means the image carries the vectors, and starting the container only
    has to write them into the graph.
    """
    from bench.embeddings import MODEL, REVISION, LocalEmbedder
    from guide.graph.refresh import EmbeddingCache, _embed

    store = EmbeddingCache(cache, f"{MODEL}@{REVISION}")
    try:
        _, embedded, reused = _embed(export, LocalEmbedder(), store)
    finally:
        store.close()
    return {"embedded": embedded, "reused": reused, "cache": str(cache)}


def _summary(report: dict) -> dict:
    return {
        "ok": True,
        "report_id": report["report_id"],
        "question_count": report["question_count"],
        "strategies": {
            name: {
                "outcomes": arm["outcomes"],
                "id_recall": arm["metrics"]["id_recall"]["value"],
                "faithfulness": arm["metrics"]["faithfulness"]["value"],
                "forbidden": {
                    b: c["occurrences"] for b, c in arm["forbidden"].items() if c["occurrences"]
                },
            }
            for name, arm in report["strategies"].items()
        },
    }


def _refresh_from_env(export, cache: Path):
    """The real thing: local Neo4j, local embedding model. Imported here so
    `--check` and the tests need neither."""
    from bench.embeddings import MODEL, REVISION, LocalEmbedder
    from bench.graph.store import driver_from_env
    from guide.graph.refresh import refresh

    driver = driver_from_env()
    try:
        return refresh(
            driver, export, LocalEmbedder(), model_id=f"{MODEL}@{REVISION}", cache_path=cache
        )
    finally:
        driver.close()


def main(
    argv=None,
    *,
    run_refresh=_refresh_from_env,
    run_eval=_eval_from_env,
    run_rescore=None,
    run_mcp=None,
    run_embed=None,
    store=None,
) -> int:
    args = parser().parse_args(argv)
    run_rescore = run_rescore or _rescore_from_env
    run_mcp = run_mcp or _mcp_from_env
    run_embed = run_embed or _embed_from_env
    try:
        if args.command == "eval":
            print(json.dumps(_summary(run_eval(args)), ensure_ascii=False))
            return 0
        if args.command == "mcp":
            return run_mcp(args)
        if args.command == "rescore":
            print(json.dumps(_summary(run_rescore(args)), ensure_ascii=False))
            return 0
        if args.command == "publish":
            from guide.eval.store import ReportStore

            if not (store or ReportStore()).publish(args.report):
                print(
                    json.dumps({"ok": False, "cause": "no_report", "detail": args.report}),
                    file=sys.stderr,
                )
                return 1
            print(json.dumps({"ok": True, "published": args.report}))
            return 0
        # The export is verified before anything that can reach a service is
        # constructed. A bad export costs no connection and no model load.
        export = read_export(args.export)
        if args.check:
            print(
                json.dumps(
                    {"ok": True, "counts": export.counts, "export_sha256": export.sha256},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.embed_only:
            print(json.dumps({"ok": True, **run_embed(export, args.cache)}, ensure_ascii=False))
            return 0
        result = run_refresh(export, args.cache)
    except FileNotFoundError as error:
        print(
            json.dumps({"ok": False, "cause": "no_report", "detail": str(error)}), file=sys.stderr
        )
        return 1
    except QuestionSetError as error:
        print(
            json.dumps(
                {"ok": False, "cause": "question_set_invalid", "detail": str(error)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    except (ExportError, RefreshError) as error:
        # The active copy is untouched in both cases; say so, since the next
        # thing the operator wonders is whether the demo is now broken.
        print(
            json.dumps(
                {
                    "ok": False,
                    "cause": error.cause,
                    "detail": error.detail,
                    "active_copy": "unchanged",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"ok": True, **asdict(result)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
