"""Local FastAPI interface. Error responses carry causes, never rejected text."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from bench.runtime import BenchError, runtime_from_env


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=2000)
    corpus: str = Field(min_length=1, max_length=100)
    strategy: Literal["whole", "graph"]

    @field_validator("question", "corpus")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value is blank")
        return value


def create_app(runtime=None) -> FastAPI:
    owned = runtime is None

    @asynccontextmanager
    async def lifespan(app):
        if owned:
            app.state.runtime = runtime_from_env()
        try:
            yield
        finally:
            if owned:
                app.state.runtime.close()

    app = FastAPI(title="Retrieval Bench", lifespan=lifespan)
    app.state.runtime = runtime

    @app.exception_handler(BenchError)
    async def bench_error(request, error):
        return JSONResponse(
            status_code=error.status, content={"outcome": error.outcome, "cause": error.cause}
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # FastAPI's default body echoes bad input, possibly including a secret
        # pasted into the question or unknown fields.
        return JSONResponse(
            status_code=422,
            content={
                "outcome": "load_failed",
                "cause": "invalid request fields",
            },
        )

    @app.post("/bench/ask")
    def ask(body: AskRequest):
        result = app.state.runtime.ask(body.question, body.corpus, body.strategy)
        if result.outcome not in ("answered", "no_grounds"):
            raise BenchError(
                result.outcome,
                result.cause or "answer unavailable",
                422 if result.outcome == "invalid_citations" else 503,
            )
        return result.to_dict()

    @app.get("/bench/corpora")
    def list_corpora():
        return app.state.runtime.list_corpora()

    @app.post("/bench/corpora/{name}/rebuild")
    def rebuild(name: str):
        return app.state.runtime.rebuild(name)

    return app


app = create_app()
