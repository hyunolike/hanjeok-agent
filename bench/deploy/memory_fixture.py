"""Test-only runtime for the 512MiB container check. Never copied into the API image.

Uses real Neo4j, retrievers, HTTP embedding/chat adapters, SQLite and SSE.
Only provider responses are fake. The Docker network has no Internet access.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import httpx

from bench.graph.store import driver_from_env, ensure_schema, record_corpus, session
from guide.embeddings import NvidiaEmbedder


def vector(text):
    values = [0.0] * 1024
    for token in text.lower().split():
        values[int.from_bytes(hashlib.sha256(token.encode()).digest()[:2], "big") % 1024] += 1
    norm = math.hypot(*values)
    return [v / norm for v in values] if norm else [1.0, *([0.0] * 1023)]


def embedding_response(request):
    body = json.loads(request.content)
    assert body["input_type"] in ("query", "passage")
    return httpx.Response(
        200,
        json={
            "data": [
                {"index": i, "embedding": vector(text)} for i, text in enumerate(body["input"])
            ]
        },
    )


def embedder():
    return NvidiaEmbedder(
        api_key="fixture-only",
        client=httpx.Client(transport=httpx.MockTransport(embedding_response)),
    )


def seed():
    from bench.corpus.loader import LoadedDoc
    from bench.graph.build import build
    from guide.export import read_export
    from guide.graph.refresh import refresh

    driver = driver_from_env()
    for attempt in range(90):
        try:
            driver.verify_connectivity()
            break
        except Exception:
            if attempt == 89:
                raise
            time.sleep(1)
    model = embedder()
    ensure_schema(driver)
    docs = [
        LoadedDoc(path, "wiki", title, "concept", text)
        for path, title, text in (
            ("concepts/alternative-scoring.md", "대안 기준", "대안 순서는 한적이 정합니다."),
            ("concepts/congestion-diagnosis.md", "혼잡 기준", "혼잡 등급은 날짜별 예보입니다."),
            ("decisions/keep-llm-out-of-ranking.md", "순위 보존", "모델은 순위를 정하지 않습니다."),
        )
    ]
    counts = build(driver, docs, model)
    record_corpus(
        driver, "wiki", "fixture", counts.docs, counts.chunks, embedding_model=model.model_id
    )
    source = read_export(Path("/fixtures/hanjeok-export"))
    result = refresh(driver, source, model, model_id=model.model_id)
    from guide.graph import read
    from guide.graph.refresh import RefreshError

    def fail(_):
        raise RuntimeError("fixture failure before activation")

    try:
        refresh(driver, source, model, model_id="incompatible@1024", before_activate=fail)
    except RefreshError:
        pass
    else:
        raise AssertionError("failed refresh unexpectedly activated")
    assert read.active(driver).embedding_model == model.model_id
    # Exercise production-size name resolution without claiming real-data
    # retrieval quality. Only these filler names lack embeddings and links.
    extra = 13403 - result.counts["places"]
    with session(driver) as s:
        s.run(
            "UNWIND range(1, $n) AS i CREATE (p:Place {generation: $generation, "
            "corpus: 'hanjeok', id: 100000+i, name: '부하검증장소'+toString(i), "
            "name_key: '부하검증장소'+toString(i), region_label: '가상지역', "
            "has_congestion_data: false})",
            n=extra,
            generation=result.generation,
        ).consume()
        s.run(
            "MATCH (c:Corpus {name: 'hanjeok'}) SET c.counts_json = $counts",
            counts=json.dumps({**result.counts, "places": 13403}),
        ).consume()
    driver.close()
    print(json.dumps({"fixture_places": 13403, "embedding_model": model.model_id}))


def serve():
    def monitor():
        maximum = 0
        while True:
            current = int(Path("/sys/fs/cgroup/memory.current").read_text())
            maximum = max(maximum, current)
            output = Path("/tmp/fixture-memory.next.json")
            output.write_text(
                json.dumps(
                    {
                        "sampled_peak_bytes": maximum,
                        "sample_interval_ms": 20,
                    }
                )
            )
            output.replace("/tmp/fixture-memory.json")
            time.sleep(0.02)

    Thread(target=monitor, daemon=True).start()
    import uvicorn
    from langchain_openai import ChatOpenAI

    from guide.api import EnvRuntime, create_app

    calls = [0]

    def chat_response(request):
        payload = json.loads(request.content)
        user = payload["messages"][-1]["content"]
        reply = dict.fromkeys(("place_id", "date", "query", "region_code", "limit", "answer"))
        reply["citations"] = []
        if "인용오류" in user:
            reply.update(action="answer", answer="가람궁을 안내합니다.", citations=["invented"])
            calls[0] = 0
        else:
            phase = calls[0] % 3
            calls[0] += 1
            time.sleep(0.08)
            if phase == 0:
                reply.update(action="search_places", query="가람궁")
            elif phase == 1:
                reply.update(action="related_places", place_id=101, limit=3)
            else:
                reply.update(
                    action="answer",
                    answer="가람궁과 연결된 장소를 안내합니다.",
                    citations=["hanjeok:place/101"],
                )
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(reply)},
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        )

    with patch("guide.embeddings.embedder_from_env", embedder):
        runtime = EnvRuntime()
    runtime.model._chat = ChatOpenAI(
        model="fixture",
        api_key="fixture-only",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(chat_response)),
    )
    assert "torch" not in sys.modules and "sentence_transformers" not in sys.modules
    uvicorn.run(
        create_app(runtime),
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        access_log=False,
    )


if __name__ == "__main__":
    seed() if "--seed" in sys.argv else serve()
