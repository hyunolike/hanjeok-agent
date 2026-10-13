"""Read-only, content-addressed evaluation questions with canonical references."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bench.runtime import BenchError

SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: str
    question: str = Field(min_length=1, max_length=2000)
    kind: Literal["single_doc", "multi_doc", "unanswerable"]
    reference_docs: list[str]
    must_contain: list[str]
    corpus: str = Field(min_length=1, max_length=100)

    @field_validator("id")
    @classmethod
    def safe_id(cls, value):
        if not SAFE_ID.fullmatch(value):
            raise ValueError("invalid id")
        return value

    @field_validator("question", "corpus")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank field")
        return value

    @model_validator(mode="after")
    def references(self):
        refs = self.reference_docs
        for value in refs:
            path = PurePosixPath(value)
            if (
                not value
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in value
                or ":" in value
                or str(path) != value
                or path.suffix != ".md"
            ):
                raise ValueError("noncanonical reference")
        if len(refs) != len(set(refs)) or any(not x.strip() for x in self.must_contain):
            raise ValueError("invalid references or claims")
        if self.kind == "unanswerable":
            if refs or self.must_contain:
                raise ValueError("unsupported question has references")
        elif not self.must_contain or (self.kind == "single_doc" and len(refs) != 1):
            raise ValueError("missing reference claims")
        elif self.kind == "multi_doc" and len(refs) < 2:
            raise ValueError("multi-document question needs multiple references")
        return self


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    questions: list[Question] = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class QuestionSet:
    id: str
    revision: str
    questions: tuple[Question, ...]

    def validate_corpus(self, corpus: str, known_paths: set[str]) -> None:
        if any(
            q.corpus != corpus or not set(q.reference_docs) <= known_paths for q in self.questions
        ):
            raise BenchError("load_failed", "question references do not match loaded corpus", 409)


class QuestionSetLoader:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def load(self, name: str) -> QuestionSet:
        try:
            if not SAFE_ID.fullmatch(name):
                raise ValueError("invalid name")
            path = (self.root / f"{name}.yaml").resolve()
            if not path.is_relative_to(self.root) or path.stat().st_size > 1_000_000:
                raise ValueError("invalid question file")
            raw = path.read_bytes()
            parsed = _File.model_validate(yaml.safe_load(raw))
            ids = [q.id for q in parsed.questions]
            if parsed.id != name or len(ids) != len(set(ids)):
                raise ValueError("invalid question identifiers")
            return QuestionSet(
                name, "sha256:" + hashlib.sha256(raw).hexdigest(), tuple(parsed.questions)
            )
        except Exception:
            raise BenchError("load_failed", "invalid or unavailable question set", 409) from None
