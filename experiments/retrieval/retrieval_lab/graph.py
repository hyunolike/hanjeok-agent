"""Bounded relationship retrieval over verified provenance and declared seed fields."""
from collections import deque
import json
from .corpus import OPTIONAL, digest, require

ALLOWED_ORIGINS = {'verified_sidecar', 'seed_fixture'}
ALLOWED_TYPES = {'HAS_SOURCE', 'DESCRIBES', 'IN_REGION'}


def edge_signature(edge):
    return '|'.join(edge[k] for k in ('start', 'type', 'end', 'origin'))


class GraphSnapshot:
    def __init__(self, corpus):
        self.corpus, self.namespace = corpus, corpus.namespace
        self.nodes, self.edges, self.aliases = {}, [], {}
        for path in corpus.evidence_ids:
            doc = corpus.documents[path]
            key = 'document:' + path
            self.nodes[key] = dict(key=key, kind='document', path=path, namespace=self.namespace,
                                   sha256=doc.sha256, source_signatures=list(doc.source_signatures),
                                   claim_statuses=list(doc.claim_statuses), origin='verified_sidecar')
            for source in doc.sources:
                source_key = 'source:' + digest('@'.join(source))
                self.nodes[source_key] = dict(key=source_key, kind='source', path=source[0],
                                             revision=source[1], sha256=source[2], namespace=self.namespace,
                                             origin='verified_sidecar')
                self.edges.append(dict(start=key, end=source_key, type='HAS_SOURCE', origin='verified_sidecar'))
                self.aliases[source[0]] = source_key
        seed = json.loads(corpus.documents[OPTIONAL].content)
        place_key, region_key = 'place:' + seed['id'], 'region:' + seed['regionId']
        self.nodes[place_key] = dict(key=place_key, kind='place', name=seed['name'], namespace=self.namespace,
                                     origin='seed_fixture')
        # Region ID is declared in the seed. No regional descriptive/weather facts are imported.
        self.nodes[region_key] = dict(key=region_key, kind='region', name=seed['regionId'],
                                      namespace=self.namespace, origin='seed_fixture')
        self.edges.extend((dict(start='document:' + OPTIONAL, end=place_key, type='DESCRIBES', origin='seed_fixture'),
                           dict(start=place_key, end=region_key, type='IN_REGION', origin='seed_fixture')))
        self.allowed_edges = frozenset(edge_signature(e) for e in self.edges)
        self.aliases.update({seed['name']: place_key, 'Gyeongbokgung': place_key, seed['regionId']: region_key})

    def seeds(self, document_ids, targets=(), query=''):
        require(set(document_ids) <= set(self.corpus.evidence_ids), 'unverified graph seed document')
        keys = ['document:' + p for p in document_ids]
        keys += [self.aliases[t] for t in targets if t in self.aliases]
        keys += [key for alias, key in self.aliases.items() if alias in query]
        return tuple(dict.fromkeys(keys))[:9]

    def validate_request(self, keys, limit):
        require(isinstance(limit, int) and 1 <= limit <= 9, 'graph document limit must be 1..9')
        require(len(keys) <= 9 and set(keys) <= set(self.nodes), 'invalid graph seed keys')

    def validate_row(self, row):
        require(row.get('namespace') == self.namespace, 'graph namespace mismatch')
        path = row.get('path')
        require(path in self.corpus.evidence_ids, 'unverified graph document')
        doc = self.corpus.documents[path]
        require(row.get('key') == 'document:' + path and row.get('sha256') == doc.sha256, 'graph document hash drift')
        require(sorted(row.get('source_signatures', [])) == list(doc.source_signatures), 'graph source revision drift')
        return path

    def export(self):
        return dict(namespace=self.namespace, nodes=list(self.nodes.values()), edges=self.edges,
                    transportWeatherEdges=0, seedFacts='fixture-derived, not verified live tourism data')


class InProcessGraph:
    status = 'in_process_verified_snapshot; not Neo4j integration'

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def expand(self, keys, limit=9):
        self.snapshot.validate_request(keys, limit)
        queue = deque((key, 0) for key in keys)
        seen, found = set(keys), set()
        while queue:
            key, hops = queue.popleft()
            node = self.snapshot.nodes[key]
            if node['kind'] == 'document':
                found.add(self.snapshot.validate_row(node))
            if hops == 2:
                continue
            for edge in self.snapshot.edges:
                if (edge['type'] not in ALLOWED_TYPES or edge['origin'] not in ALLOWED_ORIGINS
                        or edge_signature(edge) not in self.snapshot.allowed_edges):
                    continue
                other = edge['end'] if edge['start'] == key else edge['start'] if edge['end'] == key else None
                if other and other not in seen:
                    n = self.snapshot.nodes.get(other, {})
                    if n.get('namespace') == self.snapshot.namespace and n.get('origin') in ALLOWED_ORIGINS:
                        seen.add(other)
                        queue.append((other, hops + 1))
        return tuple(sorted(found)[:limit])
