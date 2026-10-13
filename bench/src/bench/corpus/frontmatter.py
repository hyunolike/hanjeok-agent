"""YAML frontmatter at byte zero, and nothing else.

Shared by both loaders because both corpora use the same envelope, even though
the keys inside differ entirely. Parsing it twice would be two places to get the
`---` handling wrong.
"""

from __future__ import annotations

from typing import Any

import yaml

DELIM = "---"


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter, body).

    A document without frontmatter yields `({}, text)` rather than raising. Both
    corpora contain such files — READMEs, generated indexes — and the loader
    decides whether to skip them. Deciding here would hide the choice.
    """
    if not text.startswith(DELIM):
        return {}, text

    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == DELIM:
            raw = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            loaded = yaml.safe_load(raw) if raw.strip() else {}
            # A scalar or list where a mapping belongs is a malformed document,
            # not an empty one. Returning {} would make it look like a file that
            # simply has no frontmatter.
            if loaded is not None and not isinstance(loaded, dict):
                raise ValueError("frontmatter is not a mapping")
            return (loaded or {}), body

    # Opened and never closed. Treating the whole file as frontmatter would
    # silently drop the body.
    raise ValueError("frontmatter opened but never closed")


def as_list(value: Any) -> tuple[str, ...]:
    """Frontmatter lists arrive as lists, but a single-item list is often
    written as a bare scalar. Both mean one item."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(v) for v in value if v is not None)
    return (str(value),)
