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
    return root


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


def main(argv=None, *, run_refresh=_refresh_from_env) -> int:
    args = parser().parse_args(argv)
    try:
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
        result = run_refresh(export, args.cache)
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
