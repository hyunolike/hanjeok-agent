from __future__ import annotations

import importlib
import json

import pytest


def api():
    try:
        return importlib.import_module("deploy.prepare_sqlite")
    except ModuleNotFoundError:
        pytest.fail("SQLite operator preparation has not been implemented")


def test_sqlite_publication_failure_keeps_previous_manifest_and_its_blob(tmp_path, monkeypatch):
    module = api()
    raw = tmp_path / "raw.sqlite"
    raw.write_bytes(b"first database")
    target = tmp_path / "data"
    first = module.publish(target, raw, {"database_sha256": module.digest(raw), "metadata": {}})
    old_manifest = (target / "manifest.json").read_bytes()
    old_blob = (target / first["gzip_file"]).read_bytes()
    raw.write_bytes(b"next database")
    replace = module.os.replace

    def fail_manifest(source, destination):
        if destination.name == "manifest.json":
            raise OSError("simulated interruption before manifest publication")
        return replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_manifest)
    with pytest.raises(OSError):
        module.publish(target, raw, {"database_sha256": module.digest(raw), "metadata": {}})
    assert (target / "manifest.json").read_bytes() == old_manifest
    assert (target / first["gzip_file"]).read_bytes() == old_blob


def test_sqlite_unpack_checks_compressed_and_decompressed_hashes(tmp_path):
    module = api()
    raw = tmp_path / "raw.sqlite"
    raw.write_bytes(b"database")
    target = tmp_path / "data"
    module.publish(target, raw, {"database_sha256": module.digest(raw), "metadata": {}})
    output = tmp_path / "unpacked.sqlite"
    module.unpack(target, output)
    assert output.read_bytes() == b"database"
    manifest = json.loads((target / "manifest.json").read_text())
    (target / manifest["gzip_file"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        module.unpack(target, output)
    assert output.read_bytes() == b"database"


def test_sqlite_wiki_binding_rejects_reordered_identical_chunk_set():
    from dataclasses import replace

    from tests.unit.test_guide_sqlite import data

    module = api()
    _, wiki = data()
    manifest = module.chunk_bindings(wiki, "model")
    moved = replace(
        wiki, docs=(replace(wiki.docs[0], body="# 둘째\n다음\n# 첫째\n본문"), wiki.docs[1])
    )
    assert module.chunk_bindings(moved, "model") != manifest


def test_memory_verifier_rejects_wiki_only_answer_to_forecast():
    import runpy
    from pathlib import Path

    verifier = runpy.run_path(str(Path(__file__).parents[2] / "deploy/verify-sqlite-memory.py"))
    stream = [
        ("step", {"kind": "policy", "status": "ok", "produced": ["wiki:a.md"]}),
        ("answer", {"citations": [{"id": "wiki:a.md"}]}),
        ("done", {"outcome": "answered", "model": "nvidia/nemotron-3-ultra-550b-a55b"}),
    ]
    assert not verifier["validated_answer"]("forecast", 200, stream)
    stream[0] = (
        "step",
        {
            "kind": "congestion",
            "status": "ok",
            "produced": ["hanjeok:congestion/10000028@2026-11-26"],
        },
    )
    stream[1] = ("answer", {"citations": [{"id": "hanjeok:congestion/10000028@2026-11-26"}]})
    assert verifier["validated_answer"]("forecast", 200, stream)
