"""Only validated text crosses this boundary. Rejections retain no answer."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Verdict:
    outcome: str
    answer: str | None = None
    citations: tuple[str, ...] = ()
    cause: str | None = None


def validate(
    answer: str,
    citations: Sequence[str],
    known: Collection[str],
    supplied: Collection[str],
) -> Verdict:
    if not answer.strip():
        return Verdict("invalid_citations", cause="answer is empty")
    if not citations:
        return Verdict("invalid_citations", cause="answer has no citations")
    for path in citations:
        if path not in known:
            # Do not echo model-generated paths: they may contain unrelated
            # filesystem paths or secrets, and the HTTP contract forbids both.
            return Verdict("invalid_citations", cause="cited path is absent from the corpus")
        if path not in supplied:
            return Verdict("invalid_citations", cause="cited document was not supplied")
    return Verdict("answered", answer, tuple(dict.fromkeys(citations)))
