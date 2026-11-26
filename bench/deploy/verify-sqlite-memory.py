"""Run actual hosted inference against the bundled SQLite under a 512MiB cap.

Pass an operator-only env file containing NVIDIA_API_KEY, GUIDE_LIVE_MODE=live
and HANJEOK_BASE_URL. It is forwarded to Docker without printing its contents.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx


def docker(*args):
    return subprocess.check_output(["docker", *map(str, args)], text=True).strip()


def frames(text):
    result = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields and "data" in fields:
            result.append((fields["event"], json.loads(fields["data"])))
    return result


def validated_answer(kind, status, stream):
    if not stream or status != 200 or stream[-1][0] != "done":
        return False
    terminal = stream[-1][1]
    if (
        terminal.get("outcome") != "answered"
        or terminal.get("model") != "nvidia/nemotron-3-ultra-550b-a55b"
    ):
        return False
    lookup, prefix = {
        "forecast": ("congestion", "hanjeok:congestion/10000028@"),
        "policy": ("policy", "wiki:concepts/congestion-diagnosis.md"),
        "alternatives": ("alternatives", "hanjeok:alternatives/"),
        "semantic_search": ("search_places", "hanjeok:place/"),
    }[kind]
    produced = {
        id
        for event, data in stream
        if event == "step" and data.get("kind") == lookup and data.get("status") == "ok"
        for id in data.get("produced", [])
    }
    cited = {
        c["id"] for event, data in stream if event == "answer" for c in data.get("citations", [])
    }
    return any(id in produced and id.startswith(prefix) for id in cited)


def verify(args):
    name = "hanjeok-guide-sqlite-" + uuid4().hex[:8]
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "backend": "sqlite",
        "questions": [],
        "passed": False,
        "public_deployment": False,
    }
    sampler = """
import time,json,pathlib
peak=0;count=0
while not pathlib.Path('/tmp/memory.done').exists():
 peak=max(peak,int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text()))
 count+=1;time.sleep(.02)
pathlib.Path('/tmp/memory.json').write_text(json.dumps(
 {'sampled_peak_bytes':peak,'samples':count,'sample_interval_ms':20}))
"""
    started = False
    try:
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "1",
            "--env-file",
            args.env_file,
            "-e",
            "GUIDE_STORE=sqlite",
            "-p",
            "127.0.0.1::8000",
            args.image,
        )
        started = True
        docker("exec", "-d", name, "python", "-c", sampler)
        port = docker("port", name, "8000/tcp").split(":")[-1]
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=90) as client:
            ready = None
            for _ in range(60):
                try:
                    ready = client.get("/guide/ready")
                    if ready.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            if ready is None or ready.status_code != 200:
                raise RuntimeError("snapshot_not_ready")
            report["ready_http_status"] = ready.status_code
            report["status"] = client.get("/guide/status").json()
            day = (date.today() + timedelta(days=2)).isoformat()
            later = (date.today() + timedelta(days=7)).isoformat()
            questions = [
                ("forecast", f"경복궁은 {day}에 얼마나 붐벼?"),
                ("policy", "혼잡 등급은 어떤 기준으로 나눠?"),
                ("alternatives", f"여의도한강공원 대신 {later}에 갈 만한 조용한 곳 있어?"),
                ("semantic_search", "서울에서 궁궐과 전통 건물을 볼 수 있는 관광지는 어디야?"),
            ]
            for kind, question in questions:
                response = client.post(
                    "/guide/ask", json={"question": question, "strategy": "graph"}
                )
                stream = frames(response.text)
                terminal = stream[-1] if stream else ("missing", {})
                answers = [d for event, d in stream if event == "answer"]
                row = {
                    "kind": kind,
                    "question": question,
                    "http_status": response.status_code,
                    "events": [event for event, _ in stream],
                    "terminal": terminal,
                    "answers": answers,
                    "steps": [d for event, d in stream if event == "step"],
                    "answered": validated_answer(kind, response.status_code, stream),
                }
                report["questions"].append(row)
                print(json.dumps({"kind": kind, "outcome": terminal[1].get("outcome")}), flush=True)
        docker("exec", name, "touch", "/tmp/memory.done")
        for _ in range(20):
            try:
                report.update(json.loads(docker("exec", name, "cat", "/tmp/memory.json")))
                break
            except subprocess.CalledProcessError:
                time.sleep(0.1)
        report["memory_limit_bytes"] = int(docker("exec", name, "cat", "/sys/fs/cgroup/memory.max"))
        report["swap_limit_bytes"] = int(
            docker("exec", name, "cat", "/sys/fs/cgroup/memory.swap.max")
        )
        report["memory_events"] = {
            k: int(v)
            for k, v in (
                line.split()
                for line in docker("exec", name, "cat", "/sys/fs/cgroup/memory.events").splitlines()
            )
        }
        report["oom_killed"] = docker("inspect", "--format", "{{.State.OOMKilled}}", name) == "true"
        report["image"] = docker("image", "inspect", "--format", "{{.Id}}", args.image)
        report["architecture"] = docker(
            "image", "inspect", "--format", "{{.Architecture}}", args.image
        )
        report["runtime_constraints_passed"] = (
            report["memory_limit_bytes"] == 536870912
            and report["swap_limit_bytes"] == 0
            and not report["oom_killed"]
            and report["memory_events"].get("oom_kill", 0) == 0
            and report.get("sampled_peak_bytes", 536870912) < 536870912
        )
        report["passed"] = report["runtime_constraints_passed"] and all(
            row["answered"] for row in report["questions"]
        )
        report["limitations"] = [
            "amd64 emulation on ARM host",
            "four actual questions only",
            "not a full quality evaluation or long-duration load",
            "20ms sampled cgroup peak includes sampler process",
            "exact SQLite cosine replaces approximate Neo4j retrieval",
        ]
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if started:
            docker("rm", "-f", name)
    print(json.dumps({"passed": report["passed"], "peak_bytes": report.get("sampled_peak_bytes")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="hanjeok-guide:sqlite-check")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(verify(parser.parse_args()))
