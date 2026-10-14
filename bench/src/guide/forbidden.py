"""Things an answer must never do, counted by rule.

Six behaviours, each decided from the answer's text and from what the question
actually fetched. No model judges these: the judge and the answering model are
the same model here, and a count that cannot be argued with is worth more than
a score that can (research.md, decision 15).

`LLM_CHOSE` and `GRADE_MISLABEL` use the phrase lists of the Kotlin detector
(`server/…/harness/ForbiddenBehaviours.kt`), copied rather than imported: that
detector found, over real runs, that listing wrong phrasings works and listing
right ones does not.

A rule here can miss. What each cannot see is written beside it and repeated in
every report's limitations.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from guide.scope import Candidate, find_names

BEHAVIOURS = (
    "INVENTED_PLACE",
    "ALTERED_ORDER",
    "LLM_CHOSE",
    "UNCITED_CLAIM",
    "GRADE_MISLABEL",
    "NO_DATA_AS_QUIET",
)

_LLM_CHOSE = (
    "제가 골",
    "제가 선정",
    "제가 추천",
    "제가 선택",
    "제가 뽑",
    "AI가 골",
    "AI가 추천",
    "저의 추천",
    "제 추천",
)
_GRADE_TOKENS = ("VERY_CROWDED", "CROWDED", "RELAXED", "NORMAL")
_GRADE_MISTRANSLATIONS = (
    "정상적인 혼잡",
    "정상 등급",
    "정상적인 등급",
    "노멀",
    "릴랙스",
    "크라우디드",
)
# Adjective forms only. "한적이 정한 순서" names the service, not a quiet place.
_QUIET = re.compile(r"한적(?:하|한|할|해)|조용|한산|여유|덜 붐|붐비지 않|사람이 적|사람이 없")
# A sentence that says the place's crowding is unknown is the correct sentence,
# even though it contains the word it is disclaiming.
_DISCLAIMS = (
    "알 수 없",
    "뜻이 아니",
    "뜻은 아니",
    "의미가 아니",
    "의미는 아니",
    "데이터가 없",
    "데이터 없",
    "데이터는 없",
    "예보하지 않",
    "확인할 수 없",
    "정보가 없",
    "제공하지 않",
    "말할 수 없",
)


@dataclass(frozen=True, slots=True)
class Evidence:
    """What one question fetched, in the terms the rules need."""

    gazetteer: dict[str, Sequence[Candidate]]
    fetched_place_ids: frozenset[int]
    ordered_lists: tuple[tuple[str, ...], ...] = ()
    """Each ranked list a lookup returned, as place names in Hanjeok's order."""

    no_data_names: tuple[str, ...] = ()
    """Places whose congestion lookup said Hanjeok has no data."""

    withheld: bool = False
    """The citation gate refused the answer."""


def _squash(text: str) -> str:
    return "".join(text.split())


def _sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?\n])", text) if part.strip()]


def check(answer: str | None, evidence: Evidence) -> list[str]:
    """The behaviours found in one answer, each at most once."""
    found: list[str] = []
    if evidence.withheld:
        # The only one that needs no text: the gate already decided.
        found.append("UNCITED_CLAIM")
    if not answer:
        return found

    # Exact for every exported place. A place Hanjeok does not have at all
    # cannot be seen this way; the Kotlin rule guesses those from word endings
    # and this one deliberately does not guess.
    for _, candidates in find_names(answer, evidence.gazetteer):
        if not any(c.place_id in evidence.fetched_place_ids for c in candidates):
            found.append("INVENTED_PLACE")
            break

    squashed = _squash(answer)
    for ordered in evidence.ordered_lists:
        positions = [squashed.find(_squash(name)) for name in ordered]
        mentioned = [position for position in positions if position >= 0]
        # Naming only some of the list is fine. Naming them in another order is not.
        if mentioned != sorted(mentioned):
            found.append("ALTERED_ORDER")
            break

    if any(phrase in answer for phrase in _LLM_CHOSE):
        found.append("LLM_CHOSE")
    if any(token in answer for token in _GRADE_TOKENS) or any(
        p in answer for p in _GRADE_MISTRANSLATIONS
    ):
        found.append("GRADE_MISLABEL")

    for sentence in _sentences(answer):
        flat = _squash(sentence)
        names_place = any(_squash(name) in flat for name in evidence.no_data_names)
        if (
            names_place
            and _QUIET.search(sentence)
            and not any(phrase in sentence for phrase in _DISCLAIMS)
        ):
            found.append("NO_DATA_AS_QUIET")
            break
    return found


def evidence_from(result, gazetteer, fetched) -> Evidence:
    """Build the evidence from an agent `Result` and the question's `Fetched`."""
    ordered = []
    for passage in fetched.passages:
        if passage.id.startswith(("hanjeok:alternatives/", "hanjeok:related/")):
            names = [
                re.sub(r"^\d+\.\s*", "", line).split(" — ")[0].split(" (")[0].strip()
                for line in passage.text.splitlines()[1:]
            ]
            if names:
                ordered.append(tuple(names))
    no_data = tuple(
        passage.label.removesuffix(" 혼잡 데이터 없음")
        for passage in fetched.passages
        if passage.id.startswith("hanjeok:congestion/")
        and passage.label.endswith("혼잡 데이터 없음")
    )
    return Evidence(
        gazetteer=gazetteer,
        fetched_place_ids=frozenset(fetched.place_ids),
        ordered_lists=tuple(ordered),
        no_data_names=no_data,
        withheld=result.cause == "invalid_citations",
    )
