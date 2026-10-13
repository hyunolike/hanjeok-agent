import json
import time

import pytest
import yaml
from fastapi.testclient import TestClient
from tests.unit.test_evaluation import Judge
from tests.unit.test_worklog_loader import write

from bench.corpus.worklog import WorklogLoader
from bench.eval.questions import QuestionSetLoader
from bench.eval.service import EvaluationService
from bench.graph.store import driver_from_env, drop_corpus
from bench.runtime import BenchError, BenchRuntime

pytestmark = pytest.mark.integration


@pytest.fixture
def worklog_runtime(tmp_path, embedder, scripted):
    for name in ("a.md", "b.md", "c.md", "d.md"):
        write(tmp_path, name, "alpha fact", status="폐기" if name == "a.md" else "완료")
    loader = WorklogLoader(tmp_path, seed=7)
    loader.name = "worklog-curve-test"
    driver = driver_from_env()
    model = scripted(
        *[
            json.dumps(
                {"outcome": "answered", "answer": "alpha fact", "citations": ["projects/test/a.md"]}
            )
        ]
        * 8
    )
    runtime = BenchRuntime(driver, embedder, model, {loader.name: loader})
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "sample.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "sample",
                "questions": [
                    {
                        "id": "q",
                        "question": "alpha fact",
                        "corpus": loader.name,
                        "kind": "single_doc",
                        "reference_docs": ["projects/test/a.md"],
                        "must_contain": ["alpha fact"],
                    }
                ],
            }
        )
    )
    service = EvaluationService(
        runtime,
        QuestionSetLoader(questions),
        tmp_path / "runs",
        tmp_path / "reports",
        judge_factory=Judge,
    )
    yield runtime, loader, service
    service.close()
    drop_corpus(driver, loader.name)
    runtime.close()


def test_real_neo4j_size_rebuilds_http_curve_and_discarded_status(worklog_runtime):
    from bench.api import create_app

    runtime, loader, service = worklog_runtime
    with TestClient(create_app(runtime, evaluation=service)) as http:
        response = http.post(
            "/bench/run", json={"corpus": loader.name, "question_set": "sample", "sizes": [2, 4]}
        )
        assert response.status_code == 202
        url = response.json()["status_url"]
        for _ in range(100):
            report = http.get(url).json()
            if report["status"] != "running":
                break
            time.sleep(0.05)
        assert report["status"] == "completed"
        assert [row["corpus_size"] for row in report["by_size"]] == [2, 4]
        assert runtime.corpus_context(loader.name)["corpus_size"] == 4
        assert len(set(row["corpus_generation"] for row in report["by_size"])) == 2
        arms = [
            json.loads(line)
            for child in report["child_report_ids"]
            for line in (service.runs_root / f"{child}.jsonl").read_text().splitlines()
        ]
        whole = [row for row in arms if row["strategy"] == "whole"]
        assert all(row["outcome"] == "answered" for row in whole)
        assert all(
            any(
                p["attrs"]["status"] == "폐기"
                for p in json.loads(row["inputs"]["user"])["supplied"]
            )
            for row in whole
        )
        assert (
            report["by_size"][1]["strategies"]["whole"]["supplied_bytes"]["mean"]
            > report["by_size"][0]["strategies"]["whole"]["supplied_bytes"]["mean"]
        )


def test_invalid_later_size_does_not_erase_real_loaded_corpus(worklog_runtime):
    runtime, loader, service = worklog_runtime
    loaded = runtime.prepare_samples(loader.name, [2], {"projects/test/a.md"})[0].loaded
    runtime.rebuild_loaded(loader.name, loaded)
    before = runtime.corpus_context(loader.name)
    with pytest.raises(BenchError):
        service.run("sample", loader.name, sizes=[2, 5])
    assert runtime.corpus_context(loader.name) == before
    assert runtime.model.calls == []
