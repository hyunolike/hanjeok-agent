"""The ids an answer may cite, and the gate that checks them.

A citation is a string with a scheme. `wiki:` names a policy document — a
reason. `hanjeok:` names a record — a fact. The screen draws the two
differently, so the distinction is carried in the id rather than guessed later.

The gate has one rule: an answer may cite only what a lookup produced **for
this question**. Not what exists in the graph, not what an earlier question
fetched. The bench's gate asks "is this path in the corpus and was it
supplied"; here the fetched set is both.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

WIKI = "wiki:"
HANJEOK = "hanjeok:"


def place(place_id: int) -> str:
    return f"hanjeok:place/{place_id}"


def related(place_id: int) -> str:
    return f"hanjeok:related/{place_id}"


def congestion(place_id: int, day: str) -> str:
    return f"hanjeok:congestion/{place_id}@{day}"


def alternatives(place_id: int, day: str) -> str:
    return f"hanjeok:alternatives/{place_id}@{day}"


def events(place_id: int, day: str | None) -> str:
    return f"hanjeok:events/{place_id}@{day}" if day else f"hanjeok:events/{place_id}"


def wiki(path: str) -> str:
    return f"wiki:{path}"


def kind_of(citation: str) -> str:
    """`policy` for a wiki page, `record` for anything from Hanjeok."""
    return "policy" if citation.startswith(WIKI) else "record"


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    citations: tuple[str, ...] = ()
    reason: str | None = None
    """Said to the model on a repair, never to the visitor. It names no id the
    model wrote: an invented id may be anything, including text that should not
    be repeated."""


def gate(text: str, citations: Sequence[str], fetched: Mapping[str, str]) -> Verdict:
    if not text.strip():
        return Verdict(False, reason="답이 비어 있습니다.")
    if not citations:
        return Verdict(
            False, reason="답에 인용이 없습니다. 조회해서 받은 id 를 하나 이상 인용해야 합니다."
        )
    unknown = sum(1 for citation in citations if citation not in fetched)
    if unknown:
        return Verdict(
            False,
            reason=f"인용 {len(citations)}개 중 {unknown}개가 이번 질문에서 조회한 id 가 아닙니다. "
            "아래 '조회한 것'에 있는 id 만 그대로 인용하세요.",
        )
    return Verdict(True, tuple(dict.fromkeys(citations)))
