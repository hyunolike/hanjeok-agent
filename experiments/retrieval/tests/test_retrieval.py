import asyncio
from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch

from retrieval_lab.corpus import Corpus, POLICIES, OPTIONAL, digest
from retrieval_lab.graph import GraphSnapshot, InProcessGraph
from retrieval_lab.guard import resolve, facts_for
from retrieval_lab.lab import RetrievalLab, ARMS, citation_valid
from retrieval_lab.neo4j_adapter import Neo4jGraph, READ_CYPHER
from retrieval_lab.ragas_eval import id_scores, judge_scores
from retrieval_lab.vector import LexicalVector, LocalSemanticVector

AGENT = Path(__file__).resolve().parents[3]
WIKI = AGENT.parent / 'travel-context-wiki'


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus(AGENT, WIKI)

    def test_full_bytes_policy_inventory(self):
        self.assertEqual(self.c.context(self.c.documents), self.c.raw)
        self.assertEqual(len(POLICIES), 8)
        self.assertEqual(len(self.c.documents), 9)
        self.assertEqual(len(self.c.verified_sources), 5)
        self.assertEqual(len(self.c.evidence_ids), 8)

    def test_unsourced_prompt_never_retrieved(self):
        with self.assertRaisesRegex(ValueError, 'unsourced'):
            self.c.evidence(['packages/hanjeok/prompt.md'])

    def test_policy_omission_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.c.context([OPTIONAL])

    def test_unverified_id_rejected(self):
        with self.assertRaises(ValueError):
            self.c.evidence(['records/weather/invented.json'])

    def test_body_hash_fails_closed(self):
        original = Path.read_bytes
        def read(p):
            data = original(p)
            return data + b'changed' if p.name == 'hanjeok-bundle.txt' else data
        with patch.object(Path, 'read_bytes', read), self.assertRaisesRegex(ValueError, 'unpinned bundle'):
            Corpus(AGENT,WIKI)

    def test_sidecar_hash_fails_closed(self):
        original = Path.read_bytes
        def read(p):
            data = original(p)
            return data + b' ' if p.name == 'hanjeok-bundle.meta.json' else data
        with patch.object(Path, 'read_bytes', read), self.assertRaisesRegex(ValueError, 'unpinned sidecar'):
            Corpus(AGENT,WIKI)

    def test_current_source_hash_fails_closed(self):
        target = WIKI / self.c.verified_sources[0][0]
        original = Path.read_bytes
        def read(p):
            return b'changed source' if p == target else original(p)
        with patch.object(Path, 'read_bytes', read), self.assertRaisesRegex(ValueError, 'source hash/revision'):
            Corpus(AGENT,WIKI)

    def test_historical_revision_hash_fails_closed(self):
        with patch('retrieval_lab.corpus.subprocess.run', return_value=subprocess.CompletedProcess([],0,stdout=b'wrong revision')):
            with self.assertRaisesRegex(ValueError, 'source hash/revision'):
                Corpus(AGENT,WIKI)

    def test_claim_states_are_not_upgraded(self):
        self.assertIn('unverified', self.c.documents[OPTIONAL].claim_statuses)


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus(AGENT,WIKI)
        cls.lab = RetrievalLab(cls.c)

    def test_all_29_original_guards(self):
        for case in self.c.suite['cases']:
            with self.subTest(case=case['id']):
                scope=resolve(case['question'],case['history'],facts_for(AGENT,self.c.suite,case))
                expected=case['expectedDecision']
                self.assertEqual(scope.fallback,expected if expected.startswith('FALLBACK_') else '')

    def test_all_arms_policy_coverage_determinism_history(self):
        extras=json.loads((AGENT/'experiments/retrieval/fixtures/graph-cases.json').read_text())['cases']
        for case in self.c.suite['cases']+extras:
            facts=facts_for(AGENT,self.c.suite,case)
            for arm in ARMS:
                with self.subTest(case=case['id'],arm=arm):
                    result=self.lab.select(arm,case['question'],case['history'],facts)
                    poisoned=[{**t,'answer':'경복궁 제주 날씨 버스 합성 근거'} for t in case['history']]
                    self.assertEqual(result,self.lab.select(arm,case['question'],poisoned,facts))
                    self.assertEqual(result,self.lab.select(arm,case['question'],case['history'],facts))
                    self.assertTrue(POLICIES <= set(result.context_ids))
                    self.assertTrue(set(case['requiredEvidencePaths']) <= set(result.context_ids))
                    self.assertLessEqual(len(result.context_ids),9)

    def test_full_is_exact_original_bytes(self):
        self.assertEqual(self.lab.select('FULL','경복궁 혼잡도',[],{}).system,self.c.raw)

    def test_tfidf_is_real_sparse_lexical_search(self):
        v=LexicalVector(self.c)
        self.assertFalse(v.semantic)
        self.assertGreater(v.matrix.nnz,0)
        self.assertEqual(v.search('경복궁 혼잡도')[0][0],OPTIONAL)
        self.assertEqual(v.search('경복궁 혼잡도'),v.search('경복궁 혼잡도'))

    def test_invalid_bounds_rejected(self):
        for value in (0,10,-1):
            with self.assertRaises(ValueError):
                self.lab.vector.search('q',value)

    def test_optional_never_enters_approved_system(self):
        r=self.lab.select('VECTOR','경복궁 혼잡도',[],{})
        self.assertNotIn(OPTIONAL,r.system)
        self.assertIn(OPTIONAL,r.user_evidence)
        self.assertIn('UNTRUSTED',r.user_evidence)

    def test_max_original_byte_reduction_is_only_501(self):
        policies=self.c.context(POLICIES)
        self.assertEqual(len(self.c.raw.encode())-len(policies.encode()),501)
        self.assertEqual(len(self.c.raw.encode()),24703)

    def test_unsupported_weather_hours_transport_abstain_all_arms(self):
        for q in ('경복궁 날씨','경복궁 운영시간','경복궁 버스 교통 관계'):
            for arm in ARMS:
                r=self.lab.select(arm,q,[],{})
                self.assertTrue(r.abstain)
                self.assertFalse(r.evidence_ids)
                self.assertFalse(r.graph_ids)

    def test_semantic_adapter_is_disabled_before_import(self):
        with self.assertRaisesRegex(ValueError,'disabled'):
            LocalSemanticVector(self.c,'missing')

    def test_omitted_unknown_empty_and_missing_policy_citations(self):
        self.assertFalse(citation_valid(POLICIES,[OPTIONAL]))
        self.assertFalse(citation_valid(POLICIES,['https://example.invalid']))
        self.assertFalse(citation_valid(POLICIES,[]))
        self.assertFalse(citation_valid(POLICIES,['packages/hanjeok/prompt.md'],'혼잡도 백분위'))
        self.assertTrue(citation_valid(POLICIES,['concepts/congestion-diagnosis.md'],'혼잡도 백분위'))


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.c=Corpus(AGENT,WIKI)
        self.s=GraphSnapshot(self.c)
        self.g=InProcessGraph(self.s)

    def test_seed_region_two_hops(self):
        self.assertEqual(self.g.expand((self.s.aliases['region:seoul-jongno'],)),(OPTIONAL,))

    def test_shared_source_is_actual_provenance(self):
        key=self.s.aliases['raw/service-snapshots/hanjeok/attractions.fixture.json']
        self.assertEqual(set(self.g.expand((key,))),{OPTIONAL,'concepts/alternative-scoring.md'})

    def test_only_allowed_edges_no_weather_transport(self):
        self.assertEqual({e['type'] for e in self.s.edges},{'HAS_SOURCE','DESCRIBES','IN_REGION'})
        self.assertEqual({e['origin'] for e in self.s.edges},{'verified_sidecar','seed_fixture'})

    def test_synthetic_and_unsupported_edges_are_isolated(self):
        key=self.s.aliases['region:seoul-jongno']
        for origin,kind in (('synthetic','IN_REGION'),('seed_fixture','BUS_ROUTE'),('seed_fixture','IN_REGION')):
            self.s.edges.append(dict(start=key,end='document:concepts/alternative-scoring.md',type=kind,origin=origin))
        self.assertEqual(self.g.expand((key,)),(OPTIONAL,))

    def test_namespace_and_hash_rejected(self):
        row=dict(self.s.nodes['document:'+OPTIONAL])
        for field,value in (('namespace','synthetic'),('sha256','0'*64),('source_signatures',[])):
            with self.assertRaises(ValueError):
                self.s.validate_row({**row,field:value})

    def mock_driver(self,rows):
        state={}
        class Record:
            def __init__(self,data): self.row=data
            def data(self): return self.row
        class Tx:
            def run(self,query,parameters):
                state.update(query=query,parameters=parameters)
                return [Record(r) for r in rows]
        class Session:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def execute_read(self,fn): return fn(Tx())
        class Driver:
            def session(self,**kwargs): state['session']=kwargs;return Session()
        return Driver(),state

    def test_neo4j_fixed_parameterized_read_contract(self):
        keys=(self.s.aliases['region:seoul-jongno'],)
        driver,state=self.mock_driver([self.s.nodes['document:'+OPTIONAL]])
        self.assertEqual(Neo4jGraph(driver,self.s).expand(keys),(OPTIONAL,))
        self.assertEqual(str(state['query']),READ_CYPHER)
        self.assertEqual(state['query'].timeout,2.0)
        self.assertEqual(state['session']['default_access_mode'],'READ')
        self.assertEqual(state['parameters']['limit'],9)
        self.assertIn('*0..2',READ_CYPHER)
        self.assertEqual(len(state['parameters']['allowed_edges']),22)
        for verb in ('CREATE','MERGE','DELETE','SET '): self.assertNotIn(verb,READ_CYPHER)

    def test_neo4j_bounds_duplicates_and_unverified_rows(self):
        keys=(self.s.aliases['region:seoul-jongno'],)
        row=self.s.nodes['document:'+OPTIONAL]
        for rows in ([row]*10,[row,row],[{**row,'sha256':'bad'}],[{**row,'source_signatures':[]}],
                     [{**row,'namespace':'synthetic'}]):
            driver,_=self.mock_driver(rows)
            with self.assertRaises(ValueError): Neo4jGraph(driver,self.s).expand(keys)
        with self.assertRaises(ValueError): self.g.expand(keys,10)
        with self.assertRaises(ValueError): self.g.expand(('invented node',))


class RagasTests(unittest.TestCase):
    def test_actual_id_metrics_without_network(self):
        row=dict(retrieved_context_ids=['a','b','b'],reference_context_ids=['b','c'])
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network prohibited')):
            scores=asyncio.run(id_scores(row))
        self.assertEqual(scores['precision'],0.5)
        self.assertEqual(scores['recall'],0.5)

    def test_empty_set_metrics_are_null_not_fake_scores(self):
        scores=asyncio.run(id_scores(dict(retrieved_context_ids=[],reference_context_ids=['a'])))
        self.assertIsNone(scores['precision'])
        self.assertEqual(scores['recall'],0.0)
        scores=asyncio.run(id_scores(dict(retrieved_context_ids=['a'],reference_context_ids=[])))
        self.assertIsNone(scores['recall'])

    def test_judge_disabled_without_clients_or_calls(self):
        with self.assertRaisesRegex(ValueError,'disabled'):
            asyncio.run(judge_scores({}))


if __name__=='__main__': unittest.main()
