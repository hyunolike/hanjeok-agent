"""Deployment-only wiring; no provisioning, credential creation or runtime graph writes."""
import os
from urllib.parse import urlparse
from neo4j import GraphDatabase,unit_of_work
from retrieval_lab.corpus import require
from retrieval_lab.neo4j_adapter import Neo4jGraph
from .index import load_index
from .engine import Engine
from .api import create_app,private_test_network

def reader_privileges(driver):
 @unit_of_work(timeout=2.0)
 def inspect(tx):
  edition=tx.run('CALL dbms.components() YIELD edition RETURN edition').single()['edition']
  row=tx.run('SHOW CURRENT USER YIELD user, roles RETURN user, roles').single()
  require(edition=='enterprise' and row and 'reader' in row['roles'] and set(row['roles'])<={'reader','PUBLIC','public'},'production graph must use Enterprise reader-only roles; READ_ACCESS is not authorization')
  return {'edition':edition,'roles':sorted(row['roles']),'runtimeWritesAllowed':False}
 with driver.session(database='system') as s:return s.execute_read(inspect)

def configured_engine(env):
 auth=env.get('RETRIEVAL_AUTH_MODE','cloud-run-iam');require(auth in ('cloud-run-iam','loopback-test','isolated-container-test'),'auth mode')
 bind=env.get('RETRIEVAL_BIND','0.0.0.0' if auth in ('cloud-run-iam','isolated-container-test') else '127.0.0.1')
 if auth=='loopback-test':require(bind=='127.0.0.1' and not env.get('K_SERVICE'),'local authentication is loopback-only and forbidden on Cloud Run')
 elif auth=='isolated-container-test':
  require(not env.get('K_SERVICE') and env.get('RETRIEVAL_LOCAL_CONTAINER_TEST')=='1' and bind=='0.0.0.0','explicit non-cloud container test marker required')
  private_test_network(env.get('RETRIEVAL_TEST_NETWORK',''))
 else:require(env.get('K_SERVICE'),'Cloud Run IAM platform required')
 index=load_index(env['RETRIEVAL_INDEX_DIR'],env['RETRIEVAL_INDEX_VERSION'],env.get('RETRIEVAL_MODEL_DIR'))
 require(index.vector.backend!='semantic' or index.vector.model is not None,'semantic model must be packaged')
 graph=None;graph_mode=env.get('RETRIEVAL_GRAPH_MODE','disabled')
 require(graph_mode in ('disabled','neo4j'),'graph mode must be disabled or actual neo4j')
 if graph_mode=='neo4j':
  uri=env['RETRIEVAL_NEO4J_URI'];parsed=urlparse(uri)
  require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,'unsafe graph URI')
  if auth=='loopback-test':require(parsed.scheme=='bolt' and parsed.hostname=='127.0.0.1' and parsed.port==17687,'only the owned local experiment Neo4j is allowed')
  elif auth=='isolated-container-test':require(parsed.scheme=='bolt' and parsed.hostname=='hanjeok-retrieval-task8' and parsed.port==7687,'only the owned isolated Docker fixture Neo4j is allowed')
  else:require(parsed.scheme in ('neo4j+s','bolt+s') and env.get('RETRIEVAL_NEO4J_USER') and env.get('RETRIEVAL_NEO4J_PASSWORD'),'TLS and existing reader credentials required')
  credentials=(env['RETRIEVAL_NEO4J_USER'],env['RETRIEVAL_NEO4J_PASSWORD']) if env.get('RETRIEVAL_NEO4J_USER') else None
  driver=GraphDatabase.driver(uri,auth=credentials,connection_timeout=1.0,connection_acquisition_timeout=1.0,max_transaction_retry_time=0.0,max_connection_pool_size=1,telemetry_disabled=True)
  try:
   driver.verify_connectivity()
   if auth=='cloud-run-iam':reader_privileges(driver)
   graph=Neo4jGraph(driver,index.snapshot)
   # A pin is ready only when all source-backed documents really exist in the graph.
   got=graph.expand(tuple('document:'+p for p in index.corpus.evidence_ids),9)
   require(set(got)==set(index.corpus.evidence_ids),'graph snapshot missing or incompatible')
  except BaseException:driver.close();raise
 return Engine(index,graph),bind,auth

def main():
 import uvicorn
 engine,bind,auth=configured_engine(os.environ)
 app=create_app(engine,auth_mode=auth,local_token=os.environ.get('RETRIEVAL_LOCAL_TOKEN',''),platform_service=os.environ.get('K_SERVICE',''),test_network=os.environ.get('RETRIEVAL_TEST_NETWORK',''))
 try:
  uvicorn.run(app,host=bind,port=int(os.environ.get('PORT','8080')),workers=1,limit_concurrency=8,backlog=16,timeout_keep_alive=2,h11_max_incomplete_event_size=8192,access_log=False,ws='none',log_level='warning')
 finally:
  if engine.graph is not None:engine.graph.driver.close()

if __name__=='__main__':main()
