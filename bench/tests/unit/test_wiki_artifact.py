"""Operator artifacts must fail closed before any canonical cache is written."""

import hashlib
import json
import sqlite3
from array import array

import pytest
from deploy import wiki_artifact as artifact


def blob(first=1.0):
    return array('f', [first] + [0.0] * 1023).tobytes()


def database(path, rows):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE embedding (key TEXT PRIMARY KEY, vector BLOB)')
        db.executemany('INSERT INTO embedding VALUES (?, ?)', rows.items())


@pytest.mark.parametrize('value', [b'', blob(float('nan')), blob(0), blob(2)])
def test_invalid_vector_cannot_pass_numeric_comparison(value):
    with pytest.raises(ValueError):
        artifact.compare(value, blob())


def test_short_reference_cannot_pass_zip_comparison():
    with pytest.raises(ValueError):
        artifact.compare(blob(), array('f', [1.0]).tobytes())


def setup_caches(tmp_path):
    candidate, hosted, target = (tmp_path / n for n in ('candidate.db', 'hosted.db', 'ready.db'))
    database(candidate, {'local-a': blob(), 'local-b': blob(-1)})
    database(hosted, {'canonical-a': blob()})
    chunks = [
        {'candidate_key': 'local-a', 'canonical_key': 'canonical-a',
         'vector_sha256': hashlib.sha256(blob()).hexdigest(),
         'hosted_sha256': hashlib.sha256(blob()).hexdigest()},
        {'candidate_key': 'local-b', 'canonical_key': 'canonical-b',
         'vector_sha256': hashlib.sha256(blob(-1)).hexdigest(), 'hosted_sha256': None},
    ]
    return candidate, hosted, target, chunks


def test_promotion_preserves_hosted_bytes_and_leaves_original_cache_untouched(tmp_path):
    candidate, hosted, target, chunks = setup_caches(tmp_path)
    before = hosted.read_bytes()
    artifact.promote(candidate, hosted, target, chunks)
    with sqlite3.connect(target) as db:
        assert dict(db.execute('SELECT * FROM embedding')) == {
            'canonical-a': blob(), 'canonical-b': blob(-1),
        }
    assert hosted.read_bytes() == before


@pytest.mark.parametrize('change', ['extra', 'candidate', 'hosted'])
def test_modified_cache_is_rejected_without_creating_a_target(tmp_path, change):
    candidate, hosted, target, chunks = setup_caches(tmp_path)
    path = hosted if change == 'hosted' else candidate
    with sqlite3.connect(path) as db:
        if change == 'extra':
            db.execute('INSERT INTO embedding VALUES (?, ?)', ('unexpected', blob()))
        else:
            key = 'canonical-a' if change == 'hosted' else 'local-b'
            db.execute('UPDATE embedding SET vector=? WHERE key=?', (blob(0.5), key))
    with pytest.raises(ValueError):
        artifact.promote(candidate, hosted, target, chunks)
    assert not target.exists()


def test_loading_rejects_a_cache_changed_after_recorded_acceptance(tmp_path):
    candidate, hosted, target, chunks = setup_caches(tmp_path)
    result = artifact.promote(candidate, hosted, target, chunks)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'chunks': chunks}))
    report = tmp_path / 'promotion.json'
    result.update(accepted_for_load=True, canonical_identity=artifact.API_ID,
                  producer_identity=artifact.LOCAL_ID,
                  manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    report.write_text(json.dumps(result))
    assert len(artifact.verified_cache(target, manifest, report)) == 2
    with sqlite3.connect(target) as db:
        db.execute('DELETE FROM embedding WHERE key=?', ('canonical-b',))
    with pytest.raises(ValueError):
        artifact.verified_cache(target, manifest, report)
