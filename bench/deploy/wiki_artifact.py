"""Operator-only validation and atomic preparation of reviewed wiki artifacts.

Never imported by the API. No model aliases or serving fallback are installed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import tempfile
from array import array
from pathlib import Path

REVISION = 'e24ca1e346bcc53572bd7bdc02b3e8ebf66c197c'
API_ID = 'nvidia/nemotron-3.5-embed-1b@1024:input-type-v1:truncate-END:l2'
LOCAL_ID = (
    f'nvidia/Nemotron-3.5-Embed-1B-BF16@{REVISION}'
    ':1024:chat-template-passage-v1:cpu-fp32:l2'
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key(model: str, text: str) -> str:
    return sha(f'{model}\0{text}'.encode())


def vector(blob: bytes) -> list[float]:
    if not isinstance(blob, bytes) or len(blob) != 4096:
        raise ValueError('invalid_vector_width')
    values = list(array('f', blob))
    if any(not math.isfinite(v) for v in values) or abs(math.hypot(*values) - 1) > 1e-5:
        raise ValueError('invalid_vector_norm_or_component')
    return values


def compare(local: bytes, reference: bytes) -> dict:
    a, b = vector(local), vector(reference)
    cosine = math.fsum(x * y for x, y in zip(a, b, strict=True)) / (
        math.hypot(*a) * math.hypot(*b)
    )
    error = max(abs(x - y) for x, y in zip(a, b, strict=True))
    if not all(math.isfinite(v) for v in (cosine, error)) or cosine < 0.999 or error > 0.005:
        raise ValueError('hosted_reference_mismatch')
    return {'cosine': cosine, 'maximum_component_error': error}


def rows(path: Path) -> dict[str, bytes]:
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        result = dict(db.execute('SELECT key, vector FROM embedding'))
    for value in result.values():
        vector(value)
    return result


def checked(path: Path, expected: dict[str, str]) -> dict[str, bytes]:
    result = rows(path)
    if set(result) != set(expected) or any(sha(v) != expected[k] for k, v in result.items()):
        raise ValueError('artifact_membership_or_hash_mismatch')
    return result


def promote(candidate: Path, hosted: Path, target: Path, chunks: list[dict]) -> dict:
    """Prepare a new cache; the original seven hosted references stay untouched."""
    if target.exists() or target.resolve() in (candidate.resolve(), hosted.resolve()):
        raise ValueError('target_must_be_new')
    local_hashes = {c['candidate_key']: c['vector_sha256'] for c in chunks}
    hosted_hashes = {c['canonical_key']: c['hosted_sha256'] for c in chunks if c['hosted_sha256']}
    if len(local_hashes) != len(chunks) or len({c['canonical_key'] for c in chunks}) != len(chunks):
        raise ValueError('duplicate_chunk_keys')
    candidates, references = checked(candidate, local_hashes), checked(hosted, hosted_hashes)
    expected = {}
    for chunk in chunks:
        local_key, canonical_key = chunk['candidate_key'], chunk['canonical_key']
        if canonical_key in references:
            compare(candidates[local_key], references[canonical_key])
        expected[canonical_key] = references.get(canonical_key, candidates[local_key])
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='.wiki-stage-', dir=target.parent)
    os.close(fd)
    stage = Path(filename)
    try:
        with sqlite3.connect(stage) as db:
            db.execute('CREATE TABLE embedding (key TEXT PRIMARY KEY, vector BLOB)')
            db.executemany('INSERT INTO embedding VALUES (?, ?)', expected.items())
        checked(stage, {k: sha(v) for k, v in expected.items()})
        os.replace(stage, target)
    finally:
        stage.unlink(missing_ok=True)
    return {
        'hosted_rows_preserved': len(references),
        'offline_rows_added': len(expected) - len(references),
        'cache_sha256': sha(target.read_bytes()),
        'rows': {k: sha(v) for k, v in sorted(expected.items())},
    }


def verified_cache(cache: Path, manifest_path: Path, report_path: Path) -> dict[str, bytes]:
    """Check recorded acceptance again immediately before operator DB loading."""
    manifest, report = json.loads(manifest_path.read_text()), json.loads(report_path.read_text())
    if (report.get('accepted_for_load') is not True
            or report.get('canonical_identity') != API_ID
            or report.get('producer_identity') != LOCAL_ID
            or report.get('manifest_sha256') != sha(manifest_path.read_bytes())
            or report.get('cache_sha256') != sha(cache.read_bytes())):
        raise ValueError('artifact_acceptance_or_hash_mismatch')
    expected = {c['canonical_key']: c['hosted_sha256'] or c['vector_sha256']
                for c in manifest['chunks']}
    if report['rows'] != expected or len(expected) != len(manifest['chunks']):
        raise ValueError('accepted_row_set_mismatch')
    return checked(cache, expected)
