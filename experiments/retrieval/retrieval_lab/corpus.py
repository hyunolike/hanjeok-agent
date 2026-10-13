"""Verify pinned bytes and source Git revisions before exposing retrieval evidence."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

POLICIES = frozenset((
    'packages/hanjeok/prompt.md', 'concepts/travel-context-layer.md',
    'decisions/keep-llm-out-of-ranking.md', 'concepts/course-generation-policy.md',
    'concepts/congestion-diagnosis.md', 'concepts/alternative-scoring.md',
    'queries/why-this-place-today.md', 'records/congestion/grade-policy.json',
))
OPTIONAL = 'records/places/gyeongbokgung.json'


def digest(data):
    return sha256(data.encode('utf-8') if isinstance(data, str) else data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(path):
    p = PurePosixPath(path)
    require(not p.is_absolute() and '..' not in p.parts and ':' not in path, 'unsafe source path')
    return path


@dataclass(frozen=True)
class Document:
    path: str
    content: str
    section: str
    sha256: str
    sources: tuple
    claim_statuses: tuple

    @property
    def source_signatures(self):
        return tuple(sorted(f'{s[0]}@{s[1]}@{s[2]}' for s in self.sources))


class Corpus:
    """Integrity checks do not establish claim truth or reviewed status."""
    def __init__(self, agent, wiki):
        self.agent, self.wiki = Path(agent), Path(wiki)
        self.suite = json.loads((self.agent / 'harness/fixtures/context-selection/suite.json').read_text())
        require(self.suite['schemaVersion'] == 1, 'unsupported fixture schema')
        body = (self.agent / 'server/src/main/resources/prompts/hanjeok-bundle.txt').read_bytes()
        sidecar = (self.agent / 'server/src/main/resources/prompts/hanjeok-bundle.meta.json').read_bytes()
        require(digest(body) == self.suite['bundleSha256'], 'unpinned bundle')
        require(digest(sidecar) == self.suite['metadataSha256'], 'unpinned sidecar')
        require(set(self.suite['requiredPaths']) == POLICIES and self.suite['optionalPath'] == OPTIONAL,
                'mandatory inventory drift')
        self.raw = body.decode('utf-8')
        self.metadata = json.loads(sidecar)
        require(self.metadata['schemaVersion'] == 1 and self.metadata['bundleSha256'] == digest(body),
                'invalid metadata')
        require(re.fullmatch(r'[0-9a-f]{64}', self.metadata['provenanceSha256']), 'invalid provenance hash')
        self.namespace = 'retrieval-lab:' + digest(body)
        markers = list(re.finditer(r'^----- FILE: (.+) -----$', self.raw, re.M))
        require(len(markers) == 9 and markers[0].start() == 0, 'invalid marker inventory')
        require(len(self.metadata['documents']) == 9, 'invalid metadata inventory')
        self.documents = {}
        verified_sources = set()
        for i, marker in enumerate(markers):
            end = markers[i + 1].start() if i + 1 < len(markers) else len(self.raw)
            path = safe_path(marker[1])
            original = self.raw[marker.end() + 1:end].removesuffix('\n')
            entry = self.metadata['documents'][i]
            require(path not in self.documents and entry['path'] == path, 'duplicate/reordered document')
            require(digest(original) == entry['sha256'], 'document hash mismatch')
            require((self.wiki / path).read_bytes() == original.encode('utf-8'), 'wiki document drift')
            sources = tuple((safe_path(s['path']), s['revision'], s['sha256']) for s in entry['sources'])
            for source in sources:
                source_path, revision, source_hash = source
                require(re.fullmatch(r'[0-9a-f]{40}', revision), 'invalid revision')
                require(re.fullmatch(r'[0-9a-f]{64}', source_hash), 'invalid source hash')
                if source not in verified_sources:
                    current = (self.wiki / source_path).read_bytes()
                    historical = subprocess.run(['git', '-C', str(self.wiki), 'show', f'{revision}:{source_path}'],
                                                check=True, capture_output=True).stdout
                    require(digest(current) == source_hash == digest(historical), 'source hash/revision drift')
                    verified_sources.add(source)
            claims = entry['claims']
            require(bool(claims), 'missing claims')
            for claim in claims:
                require(claim['status'] in {'unverified', 'needs-review', 'reviewed'}, 'invalid claim state')
                require(claim['sources'] == entry['sources'], 'claim source mismatch')
                text = claim.get('quote') if claim['scope'] == 'quote' else original
                require(text is not None and text in original and digest(text) == claim['sha256'], 'claim hash drift')
            self.documents[path] = Document(path, original, self.raw[marker.start():end], entry['sha256'],
                                            sources, tuple(c['status'] for c in claims))
        require(set(self.documents) == POLICIES | {OPTIONAL}, 'unexpected nine-document corpus')
        # Unsourced prompt is mandatory policy, never separate retrieved evidence.
        self.evidence_ids = tuple(p for p, d in self.documents.items() if d.sources)
        self.verified_sources = tuple(sorted(verified_sources))

    def context(self, paths):
        paths = set(paths)
        require(POLICIES <= paths <= set(self.documents), 'invalid context inventory')
        return ''.join(d.section for p, d in self.documents.items() if p in paths)

    def evidence(self, paths):
        ids = list(dict.fromkeys(paths))
        require(set(ids) <= set(self.evidence_ids), 'unverified/unsourced retrieval evidence')
        return [self.documents[p].content for p in ids]
