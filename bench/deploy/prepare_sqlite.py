"""Operator-only snapshot packing. No credentials, network or inference calls.

Run from bench with PYTHONPATH=src:. The unpack command is also used at image
build time and needs only the standard library.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def chunk_bindings(wiki, model):
    from bench.corpus.chunk import split

    return [
        {
            "id": c.id,
            "text_sha256": hashlib.sha256(c.text.encode()).hexdigest(),
            "canonical_key": hashlib.sha256(f"{model}\0{c.text}".encode()).hexdigest(),
        }
        for d in wiki.docs
        for c in split(d.path, d.body)
    ]


def publish(directory, raw, manifest):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".publish-", dir=directory) as temp:
        stage = Path(temp)
        blob = stage / f"snapshot-{manifest['database_sha256']}.sqlite.gz"
        with (
            Path(raw).open("rb") as source,
            blob.open("wb") as destination,
            gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as compressed,
        ):
            shutil.copyfileobj(source, compressed, length=1024 * 1024)
        result = {
            **manifest,
            "gzip_file": blob.name,
            "gzip_sha256": digest(blob),
            "database_bytes": Path(raw).stat().st_size,
            "gzip_bytes": blob.stat().st_size,
        }
        target = directory / blob.name
        if target.exists():
            if digest(target) != result["gzip_sha256"]:
                raise ValueError("existing_gzip_hash")
        else:
            os.replace(blob, target)
        staged_manifest = stage / "manifest.json"
        staged_manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        # The only activation point: old manifest and its content-addressed blob
        # remain valid even if execution stops immediately before this replace.
        os.replace(staged_manifest, directory / "manifest.json")
    return result


def unpack(directory, output):
    directory, output = Path(directory), Path(output)
    manifest = json.loads((directory / "manifest.json").read_text())
    filename = manifest["gzip_file"]
    if Path(filename).name != filename or not filename.endswith(".sqlite.gz"):
        raise ValueError("invalid_gzip_filename")
    source = directory / filename
    if digest(source) != manifest["gzip_sha256"]:
        raise ValueError("compressed_hash")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".unpack-", dir=output.parent)
    os.close(fd)
    stage = Path(name)
    try:
        with gzip.open(source, "rb") as compressed, stage.open("wb") as destination:
            shutil.copyfileobj(compressed, destination, length=1024 * 1024)
        if digest(stage) != manifest["database_sha256"]:
            raise ValueError("database_hash")
        stage.chmod(0o444)
        os.replace(stage, output)
    finally:
        stage.unlink(missing_ok=True)


def prepare(args):
    from deploy.wiki_artifact import API_ID, LOCAL_ID, key, verified_cache

    from bench.corpus.wiki import WikiLoader
    from guide.export import read_export
    from guide.loader import place_text
    from guide.sqlite_store import write_snapshot

    artifact = json.loads(args.wiki_manifest.read_text())
    commit = subprocess.check_output(
        ["git", "-C", str(args.wiki), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(args.wiki), "status", "--porcelain"], text=True
    ).strip()
    if commit != artifact["wiki_commit"] or dirty:
        raise ValueError("wiki_revision_or_worktree_mismatch")
    wiki = WikiLoader(args.wiki).load()
    bindings = chunk_bindings(wiki, API_ID)
    expected = [
        {k: c[k] for k in ("id", "text_sha256", "canonical_key")} for c in artifact["chunks"]
    ]
    if bindings != expected:
        raise ValueError("wiki_chunk_binding_mismatch")
    validated = verified_cache(args.wiki_cache, args.wiki_manifest, args.wiki_promotion)
    export = read_export(args.export)
    if export.sha256 != artifact["export_sha256"]:
        raise ValueError("export_artifact_mismatch")
    places = {}
    with sqlite3.connect(args.place_cache.resolve().as_uri() + "?mode=ro", uri=True) as cache:
        for place in export.places:
            row = cache.execute(
                "SELECT vector FROM embedding WHERE key=?", (key(API_ID, place_text(place)),)
            ).fetchone()
            if row is None:
                raise ValueError("place_vector_missing")
            places[place.id] = row[0]
    vectors = {binding["id"]: validated[binding["canonical_key"]] for binding in bindings}
    provenance = {
        "embedding_model": API_ID,
        "wiki_embedding_model": API_ID,
        "wiki_revision": wiki.revision,
        "wiki_commit": commit,
        "wiki_as_of": max((d.updated.isoformat() for d in wiki.docs if d.updated), default=""),
        "wiki_embedding_producer": LOCAL_ID,
        "wiki_artifact_sha256": digest(args.wiki_manifest),
        "wiki_promotion_sha256": digest(args.wiki_promotion),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=args.output) as temp:
        raw = Path(temp) / "snapshot.sqlite"
        manifest = write_snapshot(raw, export, wiki, places, vectors, provenance)
        return publish(args.output, raw, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    for name in (
        "export",
        "place-cache",
        "wiki",
        "wiki-cache",
        "wiki-manifest",
        "wiki-promotion",
        "output",
    ):
        build.add_argument(f"--{name}", type=Path, required=True)
    unpacker = commands.add_parser("unpack")
    unpacker.add_argument("--directory", type=Path, required=True)
    unpacker.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "unpack":
        unpack(args.directory, args.output)
    else:
        print(json.dumps(prepare(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
