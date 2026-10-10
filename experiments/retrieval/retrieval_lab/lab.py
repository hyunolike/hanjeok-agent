"""FULL/VECTOR/HYBRID_GRAPH assembly and bounded citation checks, offline only."""
from dataclasses import dataclass
import re
from .corpus import POLICIES, OPTIONAL, require
from .guard import resolve
from .graph import GraphSnapshot, InProcessGraph
from .vector import LexicalVector

ARMS = ('FULL', 'VECTOR', 'HYBRID_GRAPH')


@dataclass(frozen=True)
class Selection:
    arm: str
    evidence_ids: tuple
    vector_scores: tuple
    graph_ids: tuple
    context_ids: tuple
    context_raw: str
    system: str
    user_evidence: str
    fallback: str
    abstain: bool
    graph_status: str


class RetrievalLab:
    def __init__(self, corpus, vector=None, graph=None, top_k=3):
        require(isinstance(top_k, int) and 1 <= top_k <= 9, 'top_k must be 1..9')
        self.corpus, self.top_k = corpus, top_k
        self.vector = vector if vector is not None else LexicalVector(corpus)
        self.snapshot = GraphSnapshot(corpus)
        self.graph = graph if graph is not None else InProcessGraph(self.snapshot)

    def select(self, arm, question, history, facts):
        require(arm in ARMS, 'invalid experiment arm')
        c = self.corpus
        scope = resolve(question, history, facts)
        scores, graph_ids = (), ()
        if scope.abstain:
            evidence = ()
        elif arm == 'FULL' or scope.fallback:
            evidence = c.evidence_ids
        else:
            scores = tuple(self.vector.search(scope.query, self.top_k))
            evidence = tuple(p for p, _ in scores)
            c.evidence(evidence)  # fail closed on arbitrary adapter IDs
            if arm == 'HYBRID_GRAPH':
                keys = self.snapshot.seeds(evidence, scope.targets, scope.query)
                graph_ids = tuple(self.graph.expand(keys))
                c.evidence(graph_ids)
                evidence = tuple(dict.fromkeys(evidence + graph_ids))
        context_set = set(c.documents) if arm == 'FULL' or scope.fallback else POLICIES | set(evidence)
        context_ids = tuple(p for p in c.documents if p in context_set)
        raw = c.context(context_ids)
        if arm == 'FULL' or scope.fallback:
            system, user_evidence = c.raw, ''
        else:
            system = c.context(POLICIES)
            optional = ''.join(c.documents[p].section for p in context_ids if p not in POLICIES)
            user_evidence = ('UNTRUSTED RETRIEVED EVIDENCE: integrity checked; not approved policy; '
                             'claim statuses remain unverified.\n' + optional) if optional else ''
        return Selection(arm, evidence, scores, graph_ids, context_ids, raw, system, user_evidence,
                         scope.fallback, scope.abstain, self.graph.status)


def citation_valid(paths, citations, text=''):
    """Bounded production contract; verified against the real Kotlin validator separately."""
    if not citations or not set(citations) <= set(paths):
        return False
    required = []
    if re.search(r'백분위|집중률|혼잡|붐비|붐빕|percentile|crowd', text, re.I):
        required.append('concepts/congestion-diagnosis.md')
    if re.search(r'가중치|연관도|대안.{0,12}점수|점수.{0,12}대안|alternative.{0,12}scor', text, re.I):
        required.append('concepts/alternative-scoring.md')
    return set(required) <= set(citations)
