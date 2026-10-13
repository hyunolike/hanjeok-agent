"""The seam.

Everything downstream of this module sees `LoadedDoc` and nothing else. A loader
knows about frontmatter keys, wikilink syntax and directory layout; the graph
builder, the retriever and the scorer must not. Constitution, Principle III.

The rule that keeps it honest: **nothing downstream may read a key out of
`attrs`.** Fields that only one corpus has ride in there, and the pipeline copies
the mapping onto the graph and supplies it to the model verbatim. The moment
something downstream writes `attrs["confidence"]`, the pipeline has learned a
corpus-specific name and the seam is gone — `tests/unit/test_loader_seam.py`
exists to fail when that happens.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LoadedDoc:
    """One document, in the only shape that crosses the seam."""

    path: str
    """Repo-relative, written exactly as a citation would name it."""

    corpus: str
    title: str
    doc_type: str
    """Free-form so a loader owns its vocabulary; downstream stages do not
    interpret corpus-specific document types."""

    body: str
    updated: date | None = None
    tags: tuple[str, ...] = ()
    links: tuple[str, ...] = ()
    """Paths of other documents in the same corpus. Already resolved and already
    filtered to targets that exist — an unresolved link is reported by the
    loader, not passed on as a dangling edge."""

    sources: tuple[str, ...] = ()
    """Raw evidence paths. Empty for corpora that have no evidence layer."""

    attrs: Mapping[str, Any] = field(default_factory=dict)
    """Corpus-specific fields. Carried, never interpreted."""


@dataclass(frozen=True, slots=True)
class DroppedRef:
    """A link or source that pointed at nothing.

    Reported rather than fatal. A curated corpus accumulates these honestly —
    a page is renamed, a snapshot is archived — and failing the load would mean
    the benchmark cannot run against real corpora, which are the only ones worth
    running against. They are surfaced at load time and in the rebuild response
    so they are visible rather than silent.
    """

    source_path: str
    target: str
    kind: str  # "link" | "source"


@dataclass(frozen=True, slots=True)
class LoadResult:
    docs: tuple[LoadedDoc, ...]
    dropped: tuple[DroppedRef, ...]
    revision: str
    """Git revision of the corpus at load time. Carried into every run record so
    a pair whose two halves saw different corpora can be detected instead of
    compared (data-model.md, pair validity)."""


class CorpusLoader(Protocol):
    """What a corpus must provide. Adding a corpus means adding one of these and
    nothing else."""

    name: str

    def load(self) -> LoadResult: ...


def check_unique_paths(docs: Iterable[LoadedDoc]) -> None:
    """Two documents at one path would silently merge in the graph, because
    `(corpus, path)` is the node's identity. Better to refuse the load."""
    seen: set[str] = set()
    for doc in docs:
        if doc.path in seen:
            raise ValueError(f"duplicate document path in corpus {doc.corpus!r}: {doc.path}")
        seen.add(doc.path)
