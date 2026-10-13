"""Read-only work-log corpus and nested, content-pinned document samples."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from bench.corpus.frontmatter import as_list, parse
from bench.corpus.loader import DroppedRef, LoadedDoc, LoadResult, check_unique_paths
from bench.corpus.wiki import WIKILINK, _as_date

CREDENTIAL = re.compile(
    r"nvapi-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|"
    r"ghp_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
REQUIRED = {"project", "type", "tech", "status"}


@dataclass(frozen=True, slots=True)
class Sample:
    loaded: LoadResult
    manifest: dict


def _hash(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


class WorklogLoader:
    name = "worklog"

    def __init__(self, root: Path, *, seed=20261012):
        self.root = Path(root).resolve()
        self.seed = seed

    def _read(self):
        if not (self.root / "projects").is_dir():
            raise ValueError("worklog projects directory is unavailable")
        documents, hashes, dropped = [], {}, []
        for path in sorted((self.root / "projects").rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            if not path.resolve().is_relative_to(self.root):
                dropped.append(DroppedRef(rel, "outside_root", "document"))
                continue
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
                front, body = parse(text)
            except Exception:
                dropped.append(DroppedRef(rel, "invalid_frontmatter", "document"))
                continue
            if not front:
                continue  # indexes/readmes are not work-log documents
            if not front.keys() >= REQUIRED:
                dropped.append(DroppedRef(rel, "invalid_metadata", "document"))
                continue
            if CREDENTIAL.search(text):
                dropped.append(DroppedRef(rel, "credential_pattern", "document"))
                continue
            heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            documents.append(
                LoadedDoc(
                    path=rel,
                    corpus=self.name,
                    title=str(front.get("title") or (heading[1] if heading else path.stem)),
                    doc_type=str(front["type"]),
                    body=body,
                    updated=_as_date(front.get("date")),
                    tags=as_list(front["tech"]),
                    sources=(),
                    attrs={"project": front["project"], "status": front["status"]},
                )
            )
            hashes[rel] = _hash(raw)
        if not documents:
            raise ValueError("worklog corpus is empty")
        check_unique_paths(documents)
        known = {d.path for d in documents}
        by_slug = {}
        for doc in documents:
            by_slug.setdefault(PurePosixPath(doc.path).stem, []).append(doc.path)
        resolved = []
        for doc in documents:
            links = []
            for match in WIKILINK.finditer(doc.body):
                target = match[1].strip()
                named = target if target.endswith(".md") else target + ".md"
                direct = (
                    named
                    if named in known
                    else posixpath.normpath(str(PurePosixPath(doc.path).parent / named))
                )
                candidates = (
                    [direct]
                    if "/" in target and direct in known
                    else by_slug.get(target.removesuffix(".md"), [])
                )
                if len(candidates) == 1:
                    if candidates[0] != doc.path and candidates[0] not in links:
                        links.append(candidates[0])
                else:
                    dropped.append(DroppedRef(doc.path, target, "link"))
            resolved.append(replace(doc, links=tuple(links)))
        revision = _hash(json.dumps(hashes, sort_keys=True, ensure_ascii=False).encode())
        return LoadResult(tuple(resolved), tuple(dropped), revision), hashes

    def load(self):
        return self._read()[0]

    def plan_samples(self, sizes, required_paths=()):
        if (
            not sizes
            or any(type(n) is not int or n < 1 for n in sizes)
            or sizes != sorted(set(sizes))
        ):
            raise ValueError("sizes must be unique positive integers in increasing order")
        loaded, hashes = self._read()
        by_path = {d.path: d for d in loaded.docs}
        anchors = sorted(set(required_paths))
        if not set(anchors) <= by_path.keys():
            raise ValueError("sample reference is absent from the safe corpus")
        if len(anchors) > sizes[0] or sizes[-1] > len(by_path):
            raise ValueError("sample size is unavailable")
        remainder = sorted(
            set(by_path) - set(anchors),
            key=lambda path: (hashlib.sha256(f"{self.seed}\0{path}".encode()).hexdigest(), path),
        )
        order = anchors + remainder
        samples = []
        for size in sizes:
            selected = set(order[:size])
            dropped = list(loaded.dropped)
            docs = []
            for path in sorted(selected):
                doc = by_path[path]
                dropped.extend(
                    DroppedRef(path, link, "outside_sample")
                    for link in doc.links
                    if link not in selected
                )
                docs.append(
                    replace(doc, links=tuple(link for link in doc.links if link in selected))
                )
            manifest = {
                "algorithm": "anchored-sha256-path-order-v1",
                "seed": self.seed,
                "population_revision": loaded.revision,
                "population_size": len(by_path),
                "size": size,
                "required_paths": anchors,
                "documents": [{"path": path, "sha256": hashes[path]} for path in sorted(selected)],
                "excluded_documents": [
                    {"path": ref.source_path, "reason": ref.target}
                    for ref in loaded.dropped
                    if ref.kind == "document"
                ],
            }
            revision = _hash(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode())
            samples.append(Sample(LoadResult(tuple(docs), tuple(dropped), revision), manifest))
        return tuple(samples)
