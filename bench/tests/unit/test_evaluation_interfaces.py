import json
from threading import Event

from fastapi.testclient import TestClient
from test_evaluation import Runtime, service


def test_http_202_progress_completed_report_and_safe_invalid_inputs(tmp_path):
    from bench.api import create_app

    entered, release = Event(), Event()
    runtime = Runtime()
    original = runtime.ask

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    runtime.ask = blocked
    svc, _, _ = service(tmp_path, runtime=runtime)
    with TestClient(create_app(runtime, evaluation=svc)) as client:
        response = client.post("/bench/run", json={"question_set": "sample", "corpus": "third"})
        assert response.status_code == 202
        job = response.json()
        assert entered.wait(5)
        progress = client.get(job["status_url"]).json()
        assert progress["status"] == "running" and progress["total"] == 2
        release.set()
        svc.close()
        assert client.get(job["status_url"]).json()["status"] == "completed"
        invalid = client.post("/bench/run", json={"question_set": "../secret", "corpus": "third"})
        assert invalid.status_code == 422 and "secret" not in invalid.text
        assert (
            client.post(
                "/bench/run", json={"question_set": "sample", "corpus": "third", "sizes": [1]}
            ).status_code
            == 409
        )
        assert client.get("/bench/reports/invalid-id").status_code == 404


def test_cli_run_and_report_read_the_same_durable_artifact_without_runtime(
    tmp_path, capsys, monkeypatch
):
    from bench.cli import main

    svc, _, _ = service(tmp_path)
    assert (
        main(
            ["run", "--question-set", "sample", "--corpus", "third"],
            runtime=svc.runtime,
            evaluation=svc,
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    report_id = report["report_id"]

    def must_not_initialize():
        raise AssertionError("report read must be offline")

    monkeypatch.setattr("bench.cli.runtime_from_env", must_not_initialize)
    assert main(["report", "--id", report_id, "--reports-root", str(tmp_path / "reports")]) == 0
    assert json.loads(capsys.readouterr().out) == report
    svc.close()
