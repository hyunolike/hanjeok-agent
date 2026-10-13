import contextlib
import json
from dataclasses import replace

import pytest
from tests.unit.test_evaluation import Runtime, service

from bench.corpus.loader import LoadedDoc, LoadResult
from bench.corpus.worklog import Sample
from bench.runtime import BenchError


class SampleRuntime(Runtime):
    def __init__(self):
        super().__init__()
        self.loaded = None
        self.rebuilds = []
        self.scope_active = False

    def supports_sampling(self, corpus):
        return corpus == "third"

    def prepare_samples(self, corpus, sizes, required_paths):
        assert required_paths == {"a.md"}
        if sizes != [2, 4]:
            raise BenchError("load_failed", "invalid samples", 409)
        return tuple(
            Sample(
                LoadResult(
                    tuple(
                        LoadedDoc(f"{chr(97 + i)}.md", corpus, "D", "note", "Fact")
                        for i in range(n)
                    ),
                    (),
                    f"rev-{n}",
                ),
                {"seed": 7, "size": n, "population_revision": "pop", "required_paths": ["a.md"]},
            )
            for n in sizes
        )

    @contextlib.contextmanager
    def evaluation_scope(self):
        self.scope_active = True
        try:
            yield
        finally:
            self.scope_active = False

    def rebuild_loaded(self, corpus, loaded):
        assert self.scope_active
        self.loaded = loaded
        self.rebuilds.append(len(loaded.docs))

    def corpus_context(self, corpus):
        assert self.loaded is not None
        return {
            "corpus": corpus,
            "corpus_revision": self.loaded.revision,
            "corpus_generation": f"g-{len(self.loaded.docs)}",
            "corpus_size": len(self.loaded.docs),
            "known_paths": {d.path for d in self.loaded.docs},
        }

    def ask(self, question, corpus, strategy):
        assert self.scope_active
        result = super().ask(question, corpus, strategy)
        profile = self.corpus_context(corpus)
        return replace(
            result,
            corpus_revision=profile["corpus_revision"],
            corpus_generation=profile["corpus_generation"],
            corpus_size=profile["corpus_size"],
        )


def test_curve_rebuilds_every_size_and_preserves_frozen_child_reports(tmp_path):
    runtime = SampleRuntime()
    svc, _, _ = service(tmp_path, runtime=runtime)
    try:
        report = svc.run("sample", "third", sizes=[2, 4])
        assert report["status"] == "completed" and report["report_type"] == "size_curve"
        assert runtime.rebuilds == [2, 4] and len(runtime.calls) == 4
        assert [row["corpus_size"] for row in report["by_size"]] == [2, 4]
        children = [svc.get(report_id) for report_id in report["child_report_ids"]]
        assert [r["corpus_revision"] for r in children] == ["rev-2", "rev-4"]
        assert all(r["included_pairs"] == 1 for r in children)
        assert all(
            row["strategies"]["whole"]["prompt_tokens"]["n"] == 1 for row in report["by_size"]
        )
        assert report["sampling"][0]["seed"] == 7
        assert not runtime.scope_active
        assert svc.get(report["report_id"]) == report
    finally:
        svc.close()


def test_all_samples_validate_before_corpus_mutation_or_model_call(tmp_path):
    runtime = SampleRuntime()
    prepare = runtime.prepare_samples

    def broken(*args):
        samples = list(prepare(*args))
        samples[1] = replace(
            samples[1], loaded=replace(samples[1].loaded, docs=samples[1].loaded.docs[1:])
        )
        return samples

    runtime.prepare_samples = broken
    svc, judge, _ = service(tmp_path, runtime=runtime)
    try:
        with pytest.raises(BenchError):
            svc.run("sample", "third", sizes=[2, 4])
        assert runtime.rebuilds == [] and runtime.calls == [] and judge.calls == []
    finally:
        svc.close()


def test_later_rebuild_failure_preserves_completed_children_and_stops(tmp_path):
    runtime = SampleRuntime()
    rebuild = runtime.rebuild_loaded

    def broken(corpus, loaded):
        if len(loaded.docs) == 4:
            raise BenchError("load_failed", "graph unavailable")
        return rebuild(corpus, loaded)

    runtime.rebuild_loaded = broken
    svc, _, _ = service(tmp_path, runtime=runtime)
    try:
        job = svc.submit("sample", "third", sizes=[2, 4])
        svc.close()
        parent = svc.get(job["report_id"])
        assert parent["status"] == "failed"
        assert len(parent["child_report_ids"]) == 1
        assert svc.get(parent["child_report_ids"][0])["status"] == "completed"
        assert runtime.rebuilds == [2] and len(runtime.calls) == 2
    finally:
        svc.close()


def test_offline_cli_by_size_uses_saved_curve_without_runtime(tmp_path, monkeypatch, capsys):
    from bench.cli import main

    runtime = SampleRuntime()
    svc, _, _ = service(tmp_path, runtime=runtime)
    try:
        report = svc.run("sample", "third", sizes=[2, 4])
        monkeypatch.setattr("bench.cli.runtime_from_env", lambda: pytest.fail("offline runtime"))
        assert (
            main(
                [
                    "report",
                    "--id",
                    report["report_id"],
                    "--reports-root",
                    str(tmp_path / "reports"),
                    "--by-size",
                ]
            )
            == 0
        )
        body = json.loads(capsys.readouterr().out)
        assert body["by_size"] == report["by_size"]
    finally:
        svc.close()


def test_arm_log_is_structured_and_does_not_contain_prompt_text(tmp_path, caplog):
    import logging

    from bench.eval.runner import PairRunner

    caplog.set_level(logging.INFO, logger="bench.runs")
    PairRunner(Runtime(), tmp_path / "runs.jsonl").pair(
        question_id="q", question="private-question-body", corpus="third"
    )
    messages = [r.message for r in caplog.records if r.name == "bench.runs"]
    assert len(messages) == 2
    rows = [json.loads(message) for message in messages]
    assert all(row["event"] == "bench.run" and row["supplied_passages"] >= 1 for row in rows)
    assert rows[0]["expanded_passages"] == 0
    assert all(row["outcome"] == "answered" and row["repair_count"] == 0 for row in rows)
    assert "private-question-body" not in "".join(messages)
    assert "Alpha fact" not in "".join(messages)


def test_curve_progress_does_not_drop_when_active_child_becomes_completed(tmp_path):
    svc, _, _ = service(tmp_path, runtime=SampleRuntime())
    execute = svc._execute
    progress = []

    def observe(*args):
        child = execute(*args)
        parent_id = next(
            key for key, value in svc._jobs.items() if value.get("report_type") == "size_curve"
        )
        progress.append(svc.get(parent_id)["completed"])
        return child

    svc._execute = observe
    try:
        svc.run("sample", "third", sizes=[2, 4])
        assert progress == [2, 4]
    finally:
        svc.close()
