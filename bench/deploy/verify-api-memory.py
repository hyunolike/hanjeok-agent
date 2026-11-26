#!/usr/bin/env python3
"""Run the API image under 512MiB against an isolated fixture Neo4j.

Requires a locally built image and Docker. No account, provider key or paid
inference is used. Creates and removes only uniquely named test resources.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout.strip()


def request(base, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def frames(text):
    result = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            result.append((fields["event"], json.loads(fields["data"])))
    return result


def exercise(base, repetitions):
    for attempt in range(90):
        try:
            status, _ = request(base, "/guide/ready")
            if status == 200:
                break
        except (OSError, urllib.error.URLError):
            pass
        if attempt == 89:
            raise RuntimeError("API did not become ready")
        time.sleep(1)
    status, body = request(base, "/guide/status")
    assert status == 200 and json.loads(body)["counts"]["places"] == 13403
    visit = None
    for _ in range(repetitions):
        status, body = request(
            base,
            "/guide/ask",
            {
                "question": "가람궁과 이어진 장소를 알려줘",
                "visit_id": visit,
            },
        )
        events = frames(body)
        assert status == 200 and events[-1][0] == "done", body
        assert [name for name, _ in events][-3:] == ["answer", "path", "done"]
        steps = {
            data["kind"]: data
            for name, data in events
            if name == "step" and data["status"] != "running"
        }
        assert {"search_places", "related_places"} <= set(steps)
        assert steps["search_places"]["status"] == "ok", steps
        assert "hanjeok:place/101" in steps["search_places"]["produced"], steps
        assert steps["related_places"]["status"] == "ok", steps
        assert "hanjeok:related/101" in steps["related_places"]["produced"], steps
        assert "hanjeok:place/118" in steps["related_places"]["produced"], steps
        visit = events[0][1]["visit_id"]
    status, body = request(
        base,
        "/guide/ask",
        {
            "question": "가람궁 인용오류",
            "visit_id": visit,
        },
    )
    events = frames(body)
    assert status == 200 and all(name != "answer" for name, _ in events)
    assert events[-1][1]["cause"] == "invalid_citations"
    # Headers arrive before the synchronous model finishes. A second
    # request for the same visit must not enter the checkpointer.
    req = urllib.request.Request(
        base + "/guide/ask",
        data=json.dumps(
            {
                "question": "가람궁과 이어진 장소를 알려줘",
                "visit_id": visit,
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        assert response.readline().startswith(b"event: visit")
        busy, _ = request(
            base,
            "/guide/ask",
            {
                "question": "가람궁을 알려줘",
                "visit_id": visit,
            },
        )
        assert busy == 429
        response.read()
    limited = 0
    for _ in range(10):
        status, _ = request(base, "/guide/ask", {"question": "가람궁을 알려줘"})
        limited += status == 429
    assert limited > 0
    return {"questions": repetitions, "busy_status": busy, "visit_limit_rejections": limited}


def verify(image, repetitions):
    root = Path(__file__).resolve().parents[1]
    prefix = f"hanjeok-memory-{uuid4().hex[:10]}"
    network, graph, api, seed, client_name = (
        f"{prefix}-{part}" for part in ("net", "graph", "api", "seed", "client")
    )
    env = [
        "BENCH_NEO4J_URI=bolt://neo4j:7687",
        "BENCH_NEO4J_USER=neo4j",
        "BENCH_NEO4J_PASSWORD=memory-check-only",
        "NVIDIA_API_KEY=fixture-only",
        "GUIDE_CORS_ALLOWED_ORIGINS=http://localhost",
        "GUIDE_LIVE_MODE=replay",
        "GUIDE_LIVE_RECORDING=/fixtures/hanjeok-live",
        "BENCH_REQUEST_INTERVAL_SECONDS=0",
        "GUIDE_LIMIT_PER_VISITOR=200",
        "GUIDE_LIMIT_PER_DAY=300",
        "GUIDE_MAX_VISITS=8",
    ]
    options = ["--network", network]
    for item in env:
        options += ["-e", item]
    options += [
        "-v",
        f"{root / 'deploy'}:/checks:ro",
        "-v",
        f"{root / 'tests/fixtures'}:/fixtures:ro",
    ]
    try:
        networks = docker("network", "ls", "-q").split()
        used = [
            ipaddress.ip_network(item["Subnet"])
            for net in json.loads(docker("network", "inspect", *networks))
            # Docker reports `"Config": null` for networks without a subnet.
            for item in (net.get("IPAM") or {}).get("Config") or []
            if item.get("Subnet")
        ]
        subnet = next(
            ipaddress.ip_network(f"10.253.{i}.0/24")
            for i in range(1, 255)
            if not any(
                ipaddress.ip_network(f"10.253.{i}.0/24").overlaps(existing)
                for existing in used
                if existing.version == 4
            )
        )
        docker("network", "create", "--internal", "--subnet", str(subnet), network)
        docker(
            "run",
            "-d",
            "--name",
            graph,
            "--network",
            network,
            "--network-alias",
            "neo4j",
            "--memory",
            "1536m",
            "-e",
            "NEO4J_AUTH=neo4j/memory-check-only",
            "-e",
            "NEO4J_server_memory_heap_initial__size=256m",
            "-e",
            "NEO4J_server_memory_heap_max__size=512m",
            "-e",
            "NEO4J_server_memory_pagecache_size=128m",
            "neo4j:5.26",
        )
        docker(
            "run",
            "--rm",
            "--name",
            seed,
            *options,
            "--entrypoint",
            "python",
            image,
            "/checks/memory_fixture.py",
            "--seed",
        )
        docker(
            "run",
            "-d",
            "--name",
            api,
            *options,
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "1",
            "--network-alias",
            "api",
            "--entrypoint",
            "python",
            image,
            "/checks/memory_fixture.py",
        )
        docker(
            "run",
            "--rm",
            "--name",
            client_name,
            "--network",
            network,
            "-v",
            f"{root / 'deploy'}:/checks:ro",
            "--entrypoint",
            "python",
            image,
            "/checks/verify-api-memory.py",
            "--base-url",
            "http://api:8000",
            "--repetitions",
            str(repetitions),
        )
        installed = json.loads(
            docker(
                "exec",
                api,
                "python",
                "-c",
                "import importlib.metadata,json; print(json.dumps(sorted("
                "d.metadata['Name'].lower() for d in importlib.metadata.distributions())))",
            )
        )
        assert not {"torch", "sentence-transformers", "ragas"} & set(installed)
        sample = json.loads(docker("exec", api, "cat", "/tmp/fixture-memory.json"))
        limit = int(docker("exec", api, "cat", "/sys/fs/cgroup/memory.max"))
        peak_raw = docker("exec", api, "cat", "/sys/fs/cgroup/memory.peak", check=False)
        peak = int(peak_raw) if peak_raw.isdigit() else None
        oom = docker("inspect", "--format", "{{.State.OOMKilled}}", api)
        assert limit == 512 * 1024 * 1024 and oom == "false"
        assert sample["sampled_peak_bytes"] < limit
        return {
            "status": "passed",
            "image": docker("image", "inspect", "--format", "{{.Id}}", image),
            "architecture": docker("image", "inspect", "--format", "{{.Architecture}}", image),
            "memory_limit_bytes": limit,
            "kernel_peak_bytes": peak,
            **sample,
            "repeated_questions": repetitions,
            "fixture_places": 13403,
            "scenarios": [
                "ready",
                "vector_search",
                "graph_lookup",
                "verified_sse",
                "invalid_citations",
                "same_visit_busy",
                "visit_capacity",
            ],
            "external_inference": "mocked",
            "database": "local Neo4j 5.26 in separate container",
            "limitations": [
                "No real NVIDIA/Aura call or 60-question quality evaluation",
                "Synthetic names at production count; only 41 embedded fixture places",
                "Sampled peak includes test instrumentation; not a concurrency benchmark",
            ],
        }
    except BaseException:
        print(docker("logs", api, check=False)[-3000:])
        raise
    finally:
        for container in (client_name, api, seed, graph):
            docker("rm", "-f", container, check=False)
        docker("network", "rm", network, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="hanjeok-guide:512mb-check")
    parser.add_argument("--repetitions", type=int, default=50, choices=range(1, 101))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--base-url")
    args = parser.parse_args()
    if args.base_url:
        print(json.dumps(exercise(args.base_url, args.repetitions)))
        raise SystemExit(0)
    if args.output is None:
        parser.error("--output is required")
    result = verify(args.image, args.repetitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
