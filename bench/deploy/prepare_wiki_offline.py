"""Reproducible operator-only wiki generation; never an API fallback.

Run from bench with PYTHONPATH=src:. See deployment/guide-free/README.md.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import resource
import sqlite3
import subprocess
import time
from array import array
from datetime import UTC, datetime
from pathlib import Path

from deploy.wiki_artifact import (
    API_ID,
    LOCAL_ID,
    REVISION,
    checked,
    compare,
    key,
    promote,
    rows,
    sha,
)

from bench.corpus.chunk import split
from bench.corpus.wiki import WikiLoader
from guide.export import read_export
from guide.loader import place_text

WIKI_REVISION = '7fc19c0c4a034868866bcf5a920e3f82050830c7'
MODEL_REPO = 'nvidia/Nemotron-3.5-Embed-1B-BF16'


def source(root):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    if git('rev-parse', 'HEAD') != WIKI_REVISION or git('status', '--porcelain'):
        raise ValueError('wiki_revision_or_worktree_mismatch')
    wiki = WikiLoader(root).load()
    chunks = [c for d in wiki.docs for c in split(d.path, d.body)]
    if len(wiki.docs) != 18 or len(chunks) != 83 or len({c.text for c in chunks}) != 83:
        raise ValueError('wiki_shape_mismatch')
    return chunks


def checkpoint(root, metadata_path):
    metadata = json.loads(metadata_path.read_text())
    if metadata['sha'] != REVISION or metadata['id'] != MODEL_REPO:
        raise ValueError('checkpoint_revision_mismatch')
    official = {f['rfilename']: f for f in metadata['siblings']}
    files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or '.cache' in path.relative_to(root).parts:
            continue
        name = path.relative_to(root).as_posix()
        info, raw = official[name], path.read_bytes()
        if info.get('lfs'):
            valid = sha(raw) == info['lfs']['sha256']
        else:
            valid = hashlib_git(raw) == info['blobId']
        if not valid:
            raise ValueError('checkpoint_file_hash_mismatch')
        files.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw),
                      'official_blob': info.get('lfs', {}).get('sha256', info.get('blobId'))})
    required = {'model-00001-of-00001.safetensors', 'model.safetensors.index.json',
                'config.json', 'tokenizer.json', 'tokenizer_config.json',
                'processor_config.json', 'chat_template.jinja'}
    if not required <= {f['path'] for f in files}:
        raise ValueError('checkpoint_files_missing')
    return files


def hashlib_git(raw):
    import hashlib
    return hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()


def generators():
    return {p.name: sha(p.read_bytes()) for p in
            (Path(__file__), Path(__file__).with_name('wiki_artifact.py'))}


def write_cache(path, values):
    if path.exists():
        raise ValueError('output_cache_must_be_new')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE embedding (key TEXT PRIMARY KEY, vector BLOB)')
        db.executemany('INSERT INTO embedding VALUES (?, ?)', values.items())


def build(args):
    # Heavy imports are confined to this operator command and its separate environment.
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    import torch
    from transformers import AutoModel, AutoProcessor

    if any(p.exists() for p in (args.manifest, args.candidate, args.anchors)):
        raise ValueError('generation_outputs_must_be_new')
    started = time.monotonic()
    generator_hashes = generators()
    files, chunks = checkpoint(args.model, args.metadata), source(args.wiki)
    hosted_wiki, hosted_places = rows(args.hosted_wiki), rows(args.hosted_places)
    if len(hosted_wiki) != 7 or not set(hosted_wiki) <= {key(API_ID, c.text) for c in chunks}:
        raise ValueError('hosted_wiki_reference_set_mismatch')
    export = read_export(args.export)
    eligible = [p for p in export.places if 50 <= len(place_text(p)) <= 1200]
    anchors = [('wiki:' + c.id, c.text, 'wiki') for c in chunks
               if key(API_ID, c.text) in hosted_wiki]
    anchors += [(f'place:{p.id}', place_text(p), 'places')
                for p in eligible[::max(1, len(eligible) // 18)][:18]]
    if len(anchors) != 25:
        raise ValueError('anchor_count_mismatch')
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True, use_fast=False)
    model = AutoModel.from_pretrained(args.model, local_files_only=True, dtype=torch.float32,
                                      attn_implementation='eager').eval()
    memo = {}

    def encode(text):
        if text not in memo:
            inputs = processor.apply_chat_template(
                [{'role': 'system', 'content': 'passage:'},
                 {'role': 'user', 'content': [{'type': 'text', 'text': text}]}],
                tokenize=True, return_dict=True, return_tensors='pt')
            tokens = inputs['input_ids'].shape[-1]
            if tokens > 10240:
                raise ValueError('input_exceeds_hosted_limit')
            with torch.inference_mode():
                hidden = model(**inputs).last_hidden_state
                mask = inputs['attention_mask'].unsqueeze(-1)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
                result = torch.nn.functional.normalize(pooled.float()[0, :1024], dim=-1)
            memo[text] = (array('f', result.tolist()).tobytes(), tokens)
        return memo[text]

    anchor_rows, proof = {}, []
    for label, text, corpus in anchors:
        local, tokens = encode(text)
        reference = (hosted_wiki if corpus == 'wiki' else hosted_places)[key(API_ID, text)]
        metrics = compare(local, reference)
        anchor_rows[key(LOCAL_ID, text)] = local
        proof.append({'id': label, 'text_sha256': sha(text.encode()), 'tokens': tokens,
                      'corpus': corpus, 'reference_key': key(API_ID, text),
                      'reference_sha256': sha(reference), 'candidate_key': key(LOCAL_ID, text),
                      'vector_sha256': sha(local), **metrics})
    candidate_rows, manifest_chunks = {}, []
    for index, chunk in enumerate(chunks):
        local, tokens = encode(chunk.text)
        canonical = key(API_ID, chunk.text)
        candidate_rows[key(LOCAL_ID, chunk.text)] = local
        manifest_chunks.append({'id': chunk.id, 'text_sha256': sha(chunk.text.encode()),
                                'tokens': tokens, 'candidate_key': key(LOCAL_ID, chunk.text),
                                'canonical_key': canonical, 'vector_sha256': sha(local),
                                'hosted_sha256': sha(hosted_wiki[canonical])
                                if canonical in hosted_wiki else None})
        if (index + 1) % 10 == 0:
            print(json.dumps({'stage': 'wiki_generated', 'count': index + 1}), flush=True)
    # Refuse a source/model/generator change during generation before binding outputs.
    if (checkpoint(args.model, args.metadata) != files or source(args.wiki) != chunks
            or generators() != generator_hashes):
        raise ValueError('source_changed_during_generation')
    write_cache(args.candidate, candidate_rows)
    write_cache(args.anchors, anchor_rows)
    checked(args.candidate, {c['candidate_key']: c['vector_sha256'] for c in manifest_chunks})
    checked(args.anchors, {c['candidate_key']: c['vector_sha256'] for c in proof})
    manifest = {
        'checked_at': datetime.now(UTC).isoformat(), 'candidate_complete': True,
        'accepted_for_load': False, 'canonical_identity': API_ID, 'producer_identity': LOCAL_ID,
        'model_revision': REVISION, 'model_files': files,
        'official_metadata_url': f'https://huggingface.co/api/models/{MODEL_REPO}/revision/'
                                 f'{REVISION}?blobs=true',
        'official_metadata_sha256': sha(args.metadata.read_bytes()),
        'wiki_commit': WIKI_REVISION, 'export_sha256': export.sha256,
        'device': 'cpu', 'dtype': 'float32', 'attention': 'eager',
        'pooling': 'attention-mask mean; first 1024; L2', 'generators': generator_hashes,
        'runtime': {p: importlib.metadata.version(p) for p in
                    ('torch', 'torchvision', 'transformers', 'pillow', 'accelerate')},
        'thresholds': {'minimum_cosine': 0.999, 'maximum_component_error': 0.005},
        'anchors': proof, 'chunks': manifest_chunks,
        'elapsed_s': round(time.monotonic() - started, 3),
        'peak_operator_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'stage': 'candidate_verified', 'chunks': len(chunks),
                      'anchors': len(proof), 'accepted_for_load': False}), flush=True)


def prepare(args):
    manifest = json.loads(args.manifest.read_text())
    if (manifest['generators'] != generators() or manifest['producer_identity'] != LOCAL_ID
            or manifest['canonical_identity'] != API_ID or not manifest['candidate_complete']
            or checkpoint(args.model, args.metadata) != manifest['model_files']
            or sha(args.metadata.read_bytes()) != manifest['official_metadata_sha256']):
        raise ValueError('manifest_provenance_mismatch')
    chunks = source(args.wiki)
    expected = [(c.id, sha(c.text.encode()), key(LOCAL_ID, c.text), key(API_ID, c.text))
                for c in chunks]
    recorded = [(c['id'], c['text_sha256'], c['candidate_key'], c['canonical_key'])
                for c in manifest['chunks']]
    if expected != recorded or any(not 0 < c['tokens'] <= 10240 for c in manifest['chunks']):
        raise ValueError('source_manifest_mismatch')
    local = checked(args.anchors, {a['candidate_key']: a['vector_sha256']
                                  for a in manifest['anchors']})
    references = {'wiki': rows(args.hosted_wiki), 'places': rows(args.hosted_places)}
    if len(manifest['anchors']) != 25:
        raise ValueError('anchor_count_mismatch')
    for anchor in manifest['anchors']:
        reference = references[anchor['corpus']][anchor['reference_key']]
        if sha(reference) != anchor['reference_sha256']:
            raise ValueError('hosted_reference_changed')
        compare(local[anchor['candidate_key']], reference)
    if not args.review.is_file() or args.report.exists():
        raise ValueError('review_required_or_report_exists')
    result = promote(args.candidate, args.hosted_wiki, args.target, manifest['chunks'])
    result.update(accepted_for_load=True, manifest_sha256=sha(args.manifest.read_bytes()),
                  review_sha256=sha(args.review.read_bytes()), canonical_identity=API_ID,
                  producer_identity=LOCAL_ID, checked_at=datetime.now(UTC).isoformat())
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'prepare'])
    for name in ('model', 'metadata', 'wiki', 'export', 'hosted-wiki', 'hosted-places',
                 'candidate', 'anchors', 'manifest', 'target', 'review', 'report'):
        parser.add_argument('--' + name, type=Path, required=name not in
                            ('export', 'target', 'review', 'report'))
    args = parser.parse_args()
    (build if args.action == 'build' else prepare)(args)


if __name__ == '__main__':
    main()
