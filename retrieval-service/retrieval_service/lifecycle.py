"""Explicit offline validation/publication. Registry never hot-reloads a running service."""
import json,os
from pathlib import Path
from .index import load_index,encoded,strict_json
from .engine import Engine
from retrieval_lab.corpus import POLICIES,require,digest
from retrieval_lab.graph import InProcessGraph

def validate_candidate(directory,version,agent,model_path=None):
 index=load_index(directory,version,model_path);engine=Engine(index,InProcessGraph(index.snapshot));agent=Path(agent)
 suite=json.loads((agent/'harness/fixtures/context-selection/suite.json').read_text());extra=json.loads((agent/'experiments/retrieval/fixtures/graph-cases.json').read_text())
 cases=suite['cases']+extra['cases'];rows=[]
 for case in cases:
  query=case.get('question',case.get('request',{}).get('question',''))
  # All fixtures must exercise policy retention and bounded source-backed IDs.
  for mode in ('VECTOR','HYBRID_GRAPH'):
   r=engine.retrieve(engine.request(query or '혼잡도 등급의 기준은 무엇인가요?',mode));ids={d['id'] for d in r['documents']}
   require(len(ids)<=9 and ids<=set(index.corpus.evidence_ids),'fixture evidence failure')
   final=set(index.corpus.documents) if r['status']!='selected' else POLICIES|ids
   require(POLICIES<=final,'mandatory policies missing');require(set(case['requiredEvidencePaths'])<=final,'fixture required evidence missing');require(not case.get('expectedAbstain') or r['status']=='abstain','unsupported fixture did not abstain');rows.append({'id':case['id'],'mode':mode,'status':r['status'],'finalIds':sorted(final)})
 report={'schemaVersion':1,'indexVersion':version,'passed':True,'fixtureCount':len(cases),'rows':rows,'graphExecution':'in_process_contract; actual Neo4j separately tested','llmJudgeRun':False}
 (Path(directory)/'validation.json').write_bytes(encoded(report));return report

def atomic_json(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);temporary=p.with_name(p.name+'.tmp')
 require(not p.is_symlink() and not temporary.exists(),'unsafe registry target');temporary.write_bytes(encoded(value));os.replace(temporary,p)

def publish(directory,version,registry):
 index=load_index(directory,version);proof=Path(directory)/'validation.json';require(proof.is_file(),'validation required');report=strict_json(proof.read_bytes())
 require(report.get('passed') is True and report.get('indexVersion')==version and report.get('fixtureCount')==35 and len(report.get('rows',[]))==70,'invalid validation report')
 p=Path(registry);state=strict_json(p.read_bytes()) if p.exists() else {'schemaVersion':1,'published':{}}
 state['published'][version]={'directory':str(Path(directory).resolve()),'identity':index.identity,'validationSha256':digest(proof.read_bytes())};state['active']=version;atomic_json(p,state);return state

def rollback(registry,version):
 p=Path(registry);state=strict_json(p.read_bytes());require(version in state['published'],'rollback version not published')
 item=state['published'][version];index=load_index(item['directory'],version);require(index.identity==item['identity'],'rollback identity drift')
 require(digest((Path(item['directory'])/'validation.json').read_bytes())==item['validationSha256'],'rollback validation drift')
 state['active']=version;atomic_json(p,state);return state
