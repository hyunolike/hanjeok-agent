"""Retrieve → answer → validate, with one bounded repair and checkpointing."""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from bench.answer.citations import validate
from bench.answer.prompt import SYSTEM, assemble
from bench.graph.query import Passage


@dataclass(frozen=True, slots=True)
class ModelReply:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    failure: Literal["refused", "malformed"] | None = None


class ChatModel(Protocol):
    def complete(self, system: str, user: str, **kwargs) -> ModelReply | str: ...


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    outcome: Literal["answered", "no_grounds"]
    answer: str | None
    citations: list[str] = Field(
        description=(
            "Copy exact repository-relative document paths from supplied[].doc only. "
            "Do not copy supplied[].chunk, append #section fragments, shorten paths, "
            "or cite raw sources."
        )
    )

    @model_validator(mode="after")
    def decline_has_no_answer(self):
        if self.outcome == "no_grounds" and (self.answer is not None or self.citations):
            raise ValueError("declined response contains an answer")
        if self.outcome == "answered" and self.answer is None:
            raise ValueError("answered response contains no answer")
        return self


@dataclass(frozen=True, slots=True)
class AnswerResult:
    run_id: str
    outcome: str
    answer: str | None
    citations: tuple[str, ...]
    supplied: tuple[Passage, ...]
    corpus_revision: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: int
    repair_count: int
    cause: str | None = None

    def to_dict(self, *, show_supplied: bool = False) -> dict:
        supplied = []
        for passage in self.supplied:
            row = {"doc": passage.doc, "chunk": passage.chunk, "chars": len(passage.text)}
            if show_supplied:
                row.update(
                    text=passage.text,
                    title=passage.title,
                    attrs=dict(passage.attrs),
                    expanded=passage.expanded,
                    score=passage.score,
                )
            supplied.append(row)
        return {
            "outcome": self.outcome,
            "answer": self.answer,
            "citations": list(self.citations),
            "supplied": supplied,
            "corpus_revision": self.corpus_revision,
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "elapsed_ms": self.elapsed_ms,
            },
        }


class State(TypedDict, total=False):
    question: str
    corpus: str
    passages: list[Passage]
    known: set[str]
    started: float
    calls: int
    repair_count: int
    prompt_tokens: int
    completion_tokens: int
    draft: ModelAnswer | None
    answer: str | None
    citations: tuple[str, ...]
    outcome: str
    cause: str | None


class AnswerPipeline:
    def __init__(
        self,
        select: Callable[[str, str], Sequence[Passage]],
        model: ChatModel,
        *,
        max_model_calls: int = 2,
        deadline_ms: int = 60_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_model_calls < 1 or deadline_ms < 1:
            raise ValueError("invalid answer budget")
        self.select, self.model = select, model
        self.max_model_calls, self.deadline_ms, self.clock = max_model_calls, deadline_ms, clock
        builder = StateGraph(State)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("answer", self._answer)
        builder.add_node("validate", self._validate)
        builder.add_node("repair", self._repair)
        builder.add_edge(START, "retrieve")
        builder.add_conditional_edges(
            "retrieve", lambda s: "answer" if s["passages"] else END, {"answer": "answer", END: END}
        )
        builder.add_edge("answer", "validate")
        builder.add_conditional_edges("validate", self._route, {"repair": "repair", END: END})
        builder.add_edge("repair", "answer")
        self.graph = builder.compile(checkpointer=InMemorySaver())

    def _retrieve(self, state: State) -> dict:
        passages = list(self.select(state["corpus"], state["question"]))
        return {"passages": passages, "outcome": "pending" if passages else "no_grounds"}

    def _answer(self, state: State) -> dict:
        if (
            state["calls"] >= self.max_model_calls
            or (self.clock() - state["started"]) * 1000 >= self.deadline_ms
        ):
            return {
                "outcome": "budget_exhausted",
                "draft": None,
                "answer": None,
                "citations": (),
                "cause": "answer call budget or deadline exhausted",
            }
        try:
            reply = self.model.complete(
                SYSTEM,
                assemble(
                    state["question"],
                    state["passages"],
                    state["cause"] if state["repair_count"] else None,
                ),
                timeout=max(0.001, self.deadline_ms / 1000 - (self.clock() - state["started"])),
            )
        except Exception:
            return {
                "outcome": "model_failed",
                "draft": None,
                "answer": None,
                "citations": (),
                "cause": "answering model unavailable",
            }
        if isinstance(reply, str):
            reply = ModelReply(reply)
        updates = {
            "calls": state["calls"] + 1,
            "prompt_tokens": state["prompt_tokens"] + reply.prompt_tokens,
            "completion_tokens": state["completion_tokens"] + reply.completion_tokens,
        }
        if (self.clock() - state["started"]) * 1000 >= self.deadline_ms:
            return {
                **updates,
                "outcome": "budget_exhausted",
                "draft": None,
                "answer": None,
                "citations": (),
                "cause": "answer deadline exhausted",
            }
        if reply.failure is not None:
            return {
                **updates,
                "outcome": "model_failed",
                "draft": None,
                "answer": None,
                "citations": (),
                "cause": "answering model refused"
                if reply.failure == "refused"
                else "answering model returned malformed output",
            }
        try:
            draft = ModelAnswer.model_validate_json(reply.text)
        except ValidationError:
            return {
                **updates,
                "outcome": "model_failed",
                "draft": None,
                "answer": None,
                "citations": (),
                "cause": "answering model returned malformed output",
            }
        return {**updates, "draft": draft, "outcome": "pending"}

    def _validate(self, state: State) -> dict:
        if state["outcome"] != "pending":
            return {}
        draft = state["draft"]
        assert draft is not None
        if draft.outcome == "no_grounds":
            return {
                "outcome": "no_grounds",
                "answer": None,
                "citations": (),
                "cause": None,
                "draft": None,
            }
        verdict = validate(
            draft.answer or "", draft.citations, state["known"], {p.doc for p in state["passages"]}
        )
        return {
            "outcome": verdict.outcome,
            "answer": verdict.answer,
            "citations": verdict.citations,
            "cause": verdict.cause,
            "draft": None,
        }

    @staticmethod
    def _route(state: State) -> str:
        return (
            "repair"
            if state["outcome"] == "invalid_citations" and not state["repair_count"]
            else END
        )

    @staticmethod
    def _repair(state: State) -> dict:
        return {"repair_count": 1}

    def ask(
        self, question: str, corpus: str, revision: str, known: Collection[str]
    ) -> AnswerResult:
        started, run_id = self.clock(), str(uuid4())
        state = self.graph.invoke(
            {
                "question": question,
                "corpus": corpus,
                "known": set(known),
                "started": started,
                "calls": 0,
                "repair_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "answer": None,
                "citations": (),
                "cause": None,
            },
            {"configurable": {"thread_id": run_id}},
        )
        return AnswerResult(
            run_id,
            state["outcome"],
            state["answer"],
            state["citations"],
            tuple(state["passages"]),
            revision,
            state["prompt_tokens"],
            state["completion_tokens"],
            max(0, int((self.clock() - started) * 1000)),
            state["repair_count"],
            state["cause"],
        )
