"""Loader for travel-context-wiki.

Canonical pages only. `raw/` files are evidence a page may cite, not pages a
citation may name, so they become `Source` nodes and never `Doc` nodes — the
wiki's own schema says canonical pages must not cite each other as sources, and
an answer that cited a raw snapshot would be naming something the wiki does not
consider a claim.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

from bench.corpus.frontmatter import as_list, parse
from bench.corpus.loader import DroppedRef, LoadedDoc, LoadResult, check_unique_paths

CANONICAL_DIRS = ("entities", "concepts", "comparisons", "queries", "decisions")

# `[[alternative-scoring]]` — a bare slug, no directory and no extension. The
# alias form `[[slug|text]]` is in Obsidian's syntax, so it is accepted even
# where the current corpus happens not to use it.
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


class WikiLoader:
    name = "wiki"

    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self) -> LoadResult:
        files = sorted(
            path
            for d in CANONICAL_DIRS
            for path in (self.root / d).glob("*.md")
            if (self.root / d).is_dir()
        )

        # Slug -> path, built before parsing bodies because a link may point
        # forward to a page that has not been read yet.
        by_slug: dict[str, list[str]] = {}
        for path in files:
            by_slug.setdefault(path.stem, []).append(str(path.relative_to(self.root)))

        docs: list[LoadedDoc] = []
        dropped: list[DroppedRef] = []

        for path in files:
            rel = str(path.relative_to(self.root))
            front, body = parse(path.read_text(encoding="utf-8"))
            if not front:
                # The schema requires frontmatter at byte zero on every
                # canonical page. A file without it is not a canonical page
                # whatever directory it sits in.
                continue

            links = self._resolve_links(rel, body, by_slug, dropped)
            sources = self._resolve_sources(rel, as_list(front.get("sources")), dropped)

            docs.append(
                LoadedDoc(
                    path=rel,
                    corpus=self.name,
                    title=str(front.get("title") or path.stem),
                    doc_type=str(front.get("type") or "unknown"),
                    body=body,
                    updated=_as_date(front.get("updated")),
                    tags=as_list(front.get("tags")),
                    links=links,
                    sources=sources,
                    # Everything below travels verbatim and is never read
                    # downstream. `contradictions` in particular is prose that
                    # names files inside sentences — see data-model.md for why
                    # it is not parsed into edges.
                    attrs={
                        "confidence": front.get("confidence"),
                        "contested": front.get("contested"),
                        "conflicts": list(as_list(front.get("contradictions"))),
                    },
                )
            )

        check_unique_paths(docs)
        return LoadResult(tuple(docs), tuple(dropped), revision=_git_revision(self.root))

    def _resolve_links(
        self,
        rel: str,
        body: str,
        by_slug: dict[str, list[str]],
        dropped: list[DroppedRef],
    ) -> tuple[str, ...]:
        out: list[str] = []
        for match in WIKILINK.finditer(body):
            slug = match.group(1).strip()
            targets = by_slug.get(slug, [])
            if len(targets) == 1:
                if targets[0] != rel and targets[0] not in out:
                    out.append(targets[0])
            else:
                # Nothing, or two canonical pages sharing a stem. Guessing
                # between two would invent an edge that is wrong half the time,
                # so both cases are reported and dropped.
                dropped.append(DroppedRef(rel, slug, "link"))
        return tuple(out)

    def _resolve_sources(
        self, rel: str, declared: tuple[str, ...], dropped: list[DroppedRef]
    ) -> tuple[str, ...]:
        out: list[str] = []
        for src in declared:
            if (self.root / src).is_file():
                out.append(src)
            else:
                dropped.append(DroppedRef(rel, src, "source"))
        return tuple(out)


def _as_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _git_revision(root: Path) -> str:
    """Short revision of the corpus, stamped onto every run made against it.

    A corpus with uncommitted edits reports `<rev>-dirty`: a pair run across
    such a corpus is not reproducible, and the mark is what lets a reader tell.
    """
    try:
        rev = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return f"{rev}-dirty" if dirty else rev
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a checkout. Runs stay possible; they are just not pinned to a
        # revision, and "unknown" says so instead of a plausible-looking blank.
        return "unknown"
