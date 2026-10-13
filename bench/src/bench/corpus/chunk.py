"""Splitting a document into the unit a citation can point at.

Split at markdown headings, keep the heading path, never merge across documents.

Why headings and not a fixed window: a score has to be able to show the reader
the passage that supported a claim. A window cuts mid-sentence and produces
passages that cannot be quoted back. A heading section is the smallest unit that
still describes itself.

Why never merging across documents: `Chunk -> Doc` must be total, because
citation validation and every per-document score depend on knowing which
document a passage came from. One merged chunk spanning two documents makes that
mapping ambiguous exactly where it matters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

# Fences are tracked so a `#` inside a code block is not read as a heading. A
# shell comment at the start of a line looks exactly like an H1.
FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True, slots=True)
class Chunk:
    doc_path: str
    ord: int
    heading_path: tuple[str, ...]
    """Headings from the document root down to this section. Empty for text
    that appears before the first heading."""

    text: str

    @property
    def id(self) -> str:
        """Stable across rebuilds, because SC-007 requires a rebuild to
        reproduce retrieval. Derived from position, not from content hash: an
        edit to a passage should not look like a different passage."""
        return f"{self.doc_path}#{self.ord}"


def split(doc_path: str, body: str) -> list[Chunk]:
    """Split one document body. A document with no headings yields one chunk;
    a document shorter than any heading yields one chunk. There is no minimum
    size — merging small sections would cross the boundary this function exists
    to keep."""
    sections: list[tuple[tuple[str, ...], list[str]]] = []
    stack: list[tuple[int, str]] = []
    current: list[str] = []
    current_path: tuple[str, ...] = ()
    in_fence = False

    def flush() -> None:
        if current and any(line.strip() for line in current):
            sections.append((current_path, list(current)))
        current.clear()

    for line in body.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            current.append(line)
            continue

        match = None if in_fence else HEADING.match(line)
        if match is None:
            current.append(line)
            continue

        flush()
        level, title = len(match.group(1)), match.group(2)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        current_path = tuple(t for _, t in stack)

    flush()

    return [
        Chunk(doc_path=doc_path, ord=i, heading_path=path, text="\n".join(lines).strip())
        for i, (path, lines) in enumerate(sections)
    ]
