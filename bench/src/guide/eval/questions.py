"""The stored question set for the guide, version 2.

Version 1 (`bench.eval.questions`) asks about the wiki and is unchanged. This
one asks about places and dates, so it has two things version 1 does not:

- **Dates relative to the evaluation day.** `{+4}` in a question becomes
  "10월 17일" when the evaluation runs on the 13th, and `{+4}` in a `needs` id
  becomes `2026-10-17`. A question written as "this Saturday" would mean a
  different date every week and the ids it needs could not be written down.
- **`needs`**: the citation ids an answer must rest on. They are what the
  judge-free precision and recall are computed against.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

KINDS = ("place_lookup", "alternatives", "date_comparison", "policy", "multi_place", "unsupported")
EXPECT = ("answered", "declined", "ask_user")
MIN_QUESTIONS = 60
MIN_PER_KIND = 8
_OFFSET = re.compile(r"\{\+(\d{1,2})\}")
_PLACE_ID = re.compile(r"hanjeok:(?:place|related|congestion|alternatives|events)/(\d+)")


class QuestionSetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    question: str
    kind: str
    expect: str
    needs: tuple[str, ...]

    def on(self, today: date) -> Question:
        """The question as asked on one day, with its dates filled in."""

        def spoken(match: re.Match) -> str:
            day = today + timedelta(days=int(match[1]))
            return f"{day.month}월 {day.day}일"

        def iso(match: re.Match) -> str:
            return (today + timedelta(days=int(match[1]))).isoformat()

        return Question(
            self.id,
            _OFFSET.sub(spoken, self.question),
            self.kind,
            self.expect,
            tuple(_OFFSET.sub(iso, need) for need in self.needs),
        )


@dataclass(frozen=True, slots=True)
class QuestionSet:
    id: str
    revision: str
    questions: tuple[Question, ...]

    def on(self, today: date) -> tuple[Question, ...]:
        return tuple(question.on(today) for question in self.questions)


def load(
    path: Path | str,
    *,
    place_ids: set[int] | None = None,
    wiki_paths: set[str] | None = None,
    minimum: int = MIN_QUESTIONS,
    minimum_per_kind: int = MIN_PER_KIND,
) -> QuestionSet:
    """Read and validate. `place_ids` and `wiki_paths`, when given, are what is
    actually loaded: a question that needs a record nobody can fetch would
    score zero for a reason that has nothing to do with the agent."""
    import hashlib

    raw_bytes = Path(path).read_bytes()
    try:
        raw = yaml.safe_load(raw_bytes)
        if raw["version"] != 2:
            raise QuestionSetError("this reader understands version 2 question sets")
        items = raw["questions"]
        set_id = str(raw["id"])
    except (yaml.YAMLError, KeyError, TypeError) as error:
        raise QuestionSetError(f"not a version 2 question set: {error}") from None

    questions: list[Question] = []
    for item in items:
        try:
            question = Question(
                str(item["id"]),
                str(item["question"]).strip(),
                item["kind"],
                item["expect"],
                tuple(item.get("needs") or ()),
            )
        except (KeyError, TypeError) as error:
            raise QuestionSetError(f"a question is missing {error}") from None
        if question.kind not in KINDS or question.expect not in EXPECT or not question.question:
            raise QuestionSetError(
                f"{question.id}: unknown kind or expectation, or an empty question"
            )
        if (question.kind == "unsupported") != (question.expect == "declined"):
            raise QuestionSetError(
                f"{question.id}: unsupported questions are the ones expected to be declined"
            )
        if bool(question.needs) != (question.expect == "answered"):
            raise QuestionSetError(
                f"{question.id}: only an answered question needs records, and it must name them"
            )
        for need in question.needs:
            if need.startswith("wiki:"):
                if wiki_paths is not None and need.removeprefix("wiki:") not in wiki_paths:
                    raise QuestionSetError(f"{question.id}: {need} is not a loaded wiki page")
            elif (match := _PLACE_ID.match(need)) is None:
                raise QuestionSetError(f"{question.id}: {need} is not a citation id")
            elif place_ids is not None and int(match[1]) not in place_ids:
                raise QuestionSetError(f"{question.id}: {need} names a place that is not loaded")
        questions.append(question)

    ids = [question.id for question in questions]
    if len(set(ids)) != len(ids):
        raise QuestionSetError("question ids are not unique")
    if len(questions) < minimum:
        raise QuestionSetError(f"{len(questions)} questions; at least {minimum} are required")
    counts = Counter(question.kind for question in questions)
    short = [kind for kind in KINDS if counts[kind] < minimum_per_kind]
    if short:
        raise QuestionSetError(
            f"fewer than {minimum_per_kind} questions of kind: {', '.join(short)}"
        )
    return QuestionSet(set_id, hashlib.sha256(raw_bytes).hexdigest()[:12], tuple(questions))
