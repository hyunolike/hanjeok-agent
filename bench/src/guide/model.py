"""The hosted model, asked for one structured object at a time.

Same provider, same pacing and same settings as the bench's answer model
(`bench.models`), because a second provider or a second pacer would make the
guide's numbers and the bench's incomparable. The difference is the schema: the
bench always asks for an answer, the guide asks for a next action.

No native tool calls. The schema's `action` is an enum, so a lookup that is not
offered cannot be expressed, let alone attempted.
"""

from __future__ import annotations

import time
from typing import Protocol

from bench.provider import (
    BASE_URL,
    EXTRA_BODY,
    PacingDeadline,
    ProviderFailure,
    api_key,
    diagnostic,
    request_pacer,
)


class ModelFailure(Exception):
    """No usable object came back. `kind` is a category, never provider text."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


class Model(Protocol):
    settings: dict

    def decide(self, system: str, user: str, schema: dict, *, timeout: float) -> dict: ...


class GuideModel:
    def __init__(self, *, settings: dict | None = None) -> None:
        from bench.models import _default_settings

        self.settings = dict(settings or _default_settings())
        self._chat = None

    def _client(self):
        if self._chat is None:
            from langchain_openai import ChatOpenAI

            try:
                key = api_key()
            except ValueError:
                raise ModelFailure("configuration") from None
            self._chat = ChatOpenAI(
                model=self.settings["name"],
                api_key=key,
                base_url=BASE_URL,
                extra_body=EXTRA_BODY,
                temperature=self.settings["temperature"],
                max_tokens=self.settings["max_tokens"],
                max_retries=0,
                timeout=60,
            )
        return self._chat

    def decide(self, system, user, schema, *, timeout):
        from langchain_core.messages import HumanMessage, SystemMessage
        from openai import APIError, LengthFinishReasonError

        started = time.monotonic()
        chat = self._client()
        try:
            request_pacer().wait(timeout=timeout)
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise PacingDeadline("no time left after pacing")
            result = chat.with_structured_output(
                schema, method="json_schema", strict=True, include_raw=True
            ).invoke([SystemMessage(system), HumanMessage(user)], timeout=remaining)
        except PacingDeadline:
            raise ModelFailure("deadline") from None
        except LengthFinishReasonError:
            raise ModelFailure("output_limit") from None
        except APIError as error:
            # Only the category is kept. Provider messages can carry request
            # contents, and nothing downstream needs them.
            raise ModelFailure(diagnostic(ProviderFailure(error))["kind"]) from None
        parsed = result.get("parsed")
        if not isinstance(parsed, dict) or result.get("parsing_error") is not None:
            raise ModelFailure("malformed")
        return parsed
