"""LangChain chat adapter with structured output and actual provider usage."""

import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from bench.answer.pipeline import ModelAnswer, ModelReply


class AnswerModel:
    def __init__(self, *, chat=None):
        self.chat = (
            chat
            if chat is not None
            else ChatOpenAI(
                model=os.environ.get("BENCH_ANSWER_MODEL", "gpt-4o"),
                temperature=0,
                max_tokens=800,
                max_retries=0,
                timeout=60,
            )
        )

    def complete(self, system: str, user: str, *, timeout: float = 60) -> ModelReply:
        result = self.chat.with_structured_output(
            ModelAnswer.model_json_schema(),
            method="json_schema",
            strict=True,
            include_raw=True,
        ).invoke([SystemMessage(system), HumanMessage(user)], timeout=timeout)
        parsed, raw = result["parsed"], result["raw"]
        usage = raw.usage_metadata or {}
        failure = None
        if raw.additional_kwargs.get("refusal"):
            failure = "refused"
        elif parsed is None or result.get("parsing_error") is not None:
            failure = "malformed"
        return ModelReply(
            json.dumps(parsed, ensure_ascii=False) if failure is None else "",
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            failure,
        )


class LazyAnswerModel:
    """Corpus discovery and empty retrieval must work without a provider key."""

    def __init__(self):
        self._model = None

    def complete(self, system: str, user: str, **kwargs) -> ModelReply:
        if self._model is None:
            self._model = AnswerModel()
        return self._model.complete(system, user, **kwargs)
