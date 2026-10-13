"""Explicit public-fixture loopback smoke; graph writes require owned label + opt-in."""
import argparse,json,sys,subprocess,urllib.request,urllib.error,http.client,time
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'retrieval-service'),str(ROOT/'experiments/retrieval')]
from retrieval_service.index import load_index
from retrieval_lab.live import driver_for,components,load_snapshot,verify_snapshot
from neo4j import Query
p=argparse.ArgumentParser();p.add_argument('--index',required=True);p.add_argument('--version',required=True);p.add_argument('--origin',default='http://127.0.0.1:17880');p.add_argument('--output',required=True);p.add_argument('--load-owned-graph',action='store_true');p.add_argument('--load-only',action='store_true');p.add_argument('--fault-owned-graph',action='store_true');a=p.parse_args()
u=urlparse(a.origin)
if u.scheme!='http' or u.hostname!='127.0.0.1' or u.username or u.password or u.path or u.query or u.fragment:raise ValueError('explicit loopback origin only')
index=load_index(a.index,a.version);proof={'actualHttp':False,'llmCalls':0,'identity':index.identity}
def call(path,body=None,token='local-test'):
 req=urllib.request.Request(a.origin+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=4) as f:return f.status,json.load(f)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
if a.load_owned_graph or a.fault_owned_graph:
 label=subprocess.check_output(['docker','inspect','--format','{{index .Config.Labels "purpose"}}','hanjeok-retrieval-task8'],text=True).strip()
 if label!='hanjeok-retrieval-task8':raise ValueError('refuse graph writes without owned public-fixture container label')
 if a.load_owned_graph:
  with driver_for('bolt://127.0.0.1:17687') as driver:
   version=components(driver);load_snapshot(driver,index.snapshot);proof['actualGraph']=verify_snapshot(driver,index.snapshot);proof['neo4jComponents']=version
if a.load_only:
 if not a.load_owned_graph or a.fault_owned_graph:raise ValueError('load-only requires owned graph loading and no fault check')
 Path(a.output).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print('Owned public-fixture graph loaded/verified; HTTP startup not yet tested');sys.exit(0)
request={'schemaVersion':1,'query':'경복궁 혼잡도 기준은?','mode':'HYBRID_GRAPH','identity':index.identity}
status,ready=call('/health/ready');assert status==200 and ready['identity']==index.identity and ready['graph']=='neo4j'
assert call('/v1/provenance')[1]['identity']==index.identity
assert call('/v1/retrieve',request)[0]==200
assert call('/v1/retrieve',request,token='bad')[0]==401
stale=json.loads(json.dumps(request));stale['identity']['indexVersion']='0'*64;assert call('/v1/retrieve',stale)[0]==409
assert call('/v1/retrieve',dict(request,namespace='invented'))[0]==400
assert call('/v1/retrieve',dict(request,query='가'*2000))[0]==400
assert call('/v1/retrieve',dict(request,query='경복궁 날씨 인과 관계는?'))[1]['status']=='abstain'
proof['healthProvenanceSchemaAuthBoundsAndAbstention']=True
c=http.client.HTTPConnection(u.hostname,u.port,timeout=4);start=time.monotonic()
try:
 c.putrequest('POST','/v1/retrieve');c.putheader('Authorization','Bearer local-test');c.putheader('Content-Type','application/json');c.putheader('Content-Length','2');c.endheaders();c.send(b'{');response=c.getresponse();assert response.status==408;response.read();elapsed=time.monotonic()-start;assert 1.5<=elapsed<3.2;proof['slowBodyDeadlineSeconds']=round(elapsed,3)
finally:c.close()
proof['actualHttp']=True
if a.fault_owned_graph:
 key='document:records/places/gyeongbokgung.json';original=index.snapshot.nodes[key]['sha256']
 with driver_for('bolt://127.0.0.1:17687') as driver:
  try:
   with driver.session(database='neo4j') as session:session.run(Query('MATCH (d:RetrievalNode {namespace:$ns,key:$key}) SET d.sha256=$value',timeout=2),ns=index.snapshot.namespace,key=key,value='0'*64).consume()
   assert call('/health/ready')[0]==503
   assert call('/v1/retrieve',request)==(503,{'code':'RETRIEVAL_UNAVAILABLE'})
   proof['realGraphTamperRejected']=True
  finally:
   with driver.session(database='neo4j') as session:session.run(Query('MATCH (d:RetrievalNode {namespace:$ns,key:$key}) SET d.sha256=$value',timeout=2),ns=index.snapshot.namespace,key=key,value=original).consume()
 assert call('/health/ready')[0]==200;proof['graphRestored']=True
Path(a.output).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print('Public-fixture API contract smoke passed; no LLM calls')
