"""Local FastAPI interface. Error responses carry causes, never rejected text."""

from contextlib import asynccontextmanager
from threading import RLock
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


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question_set: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    corpus: str = Field(min_length=1, max_length=100)
    sizes: list[int] | None = None

    @field_validator("corpus")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank corpus")
        return value

    @field_validator("sizes")
    @classmethod
    def positive_sizes(cls, value):
        if value is not None and (not value or any(n < 1 for n in value)):
            raise ValueError("invalid sizes")
        return value


def create_app(runtime=None, *, evaluation=None) -> FastAPI:
    owned = runtime is None
    evaluation_lock = RLock()

    @asynccontextmanager
    async def lifespan(app):
        if owned:
            app.state.runtime = runtime_from_env()
        try:
            yield
        finally:
            if app.state.evaluation is not None and evaluation is None:
                app.state.evaluation.close()
            if owned:
                app.state.runtime.close()

    app = FastAPI(title="Retrieval Bench", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.evaluation = evaluation

    def evaluations():
        from bench.eval.service import EvaluationService

        with evaluation_lock:
            if app.state.evaluation is None:
                app.state.evaluation = EvaluationService(app.state.runtime)
            return app.state.evaluation

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

    @app.post("/bench/run", status_code=202)
    def run(body: RunRequest):
        return evaluations().submit(body.question_set, body.corpus, sizes=body.sizes)

    @app.get("/bench/reports/{report_id}")
    def report(report_id: str):
        return evaluations().get(report_id)

    @app.post("/bench/corpora/{name}/rebuild")
    def rebuild(name: str):
        return app.state.runtime.rebuild(name)

    return app


app = create_app()
