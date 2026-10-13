"""LangChain chat adapter with structured output and actual provider usage."""

import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIError, LengthFinishReasonError

from bench.answer.pipeline import ModelAnswer, ModelReply
from bench.provider import BASE_URL, EXTRA_BODY, MODEL, ProviderFailure, api_key, request_pacer


def _default_settings() -> dict:
    return {
        "name": os.environ.get("BENCH_ANSWER_MODEL", MODEL),
        "provider": "nvidia",
        "base_url": BASE_URL,
        "enable_thinking": False,
        "temperature": 0,
        "max_tokens": 800,
        "minimum_request_interval_seconds": float(
            os.environ.get("BENCH_REQUEST_INTERVAL_SECONDS", "3")
        ),
    }


class AnswerModel:
    def __init__(self, *, chat=None, settings=None):
        self._settings = dict(settings or _default_settings())
        self.pacer = request_pacer() if chat is None else None
        self.chat = (
            chat
            if chat is not None
            else ChatOpenAI(
                model=self._settings["name"],
                api_key=api_key(),
                base_url=BASE_URL,
                extra_body=EXTRA_BODY,
                temperature=self._settings["temperature"],
                max_tokens=self._settings["max_tokens"],
                max_retries=0,
                timeout=60,
            )
        )
        if chat is not None:
            self._settings = {
                "name": chat.model_name,
                "temperature": chat.temperature,
                "max_tokens": chat.max_tokens,
            }

    @property
    def settings(self) -> dict:
        return dict(self._settings)

    def complete(self, system: str, user: str, *, timeout: float = 60) -> ModelReply:
        try:
            if self.pacer is not None:
                self.pacer.wait()
            result = self.chat.with_structured_output(
                ModelAnswer.model_json_schema(),
                method="json_schema",
                strict=True,
                include_raw=True,
            ).invoke([SystemMessage(system), HumanMessage(user)], timeout=timeout)
        except LengthFinishReasonError as error:
            # Native SDK parsing aborts before LangChain returns the raw message,
            # but the exception retains the completion's billed usage.
            usage = error.completion.usage
            return ModelReply(
                "",
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
                "output_limit",
            )
        except APIError as error:
            raise ProviderFailure(error) from None
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
        self._settings = _default_settings()

    @property
    def settings(self) -> dict:
        return dict(self._settings)

    def complete(self, system: str, user: str, **kwargs) -> ModelReply:
        if self._model is None:
            self._model = AnswerModel(settings=self._settings)
        return self._model.complete(system, user, **kwargs)
