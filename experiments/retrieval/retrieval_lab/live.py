"""Opt-in, isolated localhost Neo4j fixture loading and real driver checks."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from neo4j import GraphDatabase, Query, unit_of_work
from .corpus import Corpus, require, OPTIONAL
from .graph import GraphSnapshot, InProcessGraph, ALLOWED_TYPES
from .neo4j_adapter import Neo4jGraph
from .network import network_scope

URI = 'bolt://127.0.0.1:17687'


def driver_for(uri):
    parsed = urlparse(uri)
    require(parsed.scheme == 'bolt' and parsed.hostname == '127.0.0.1' and parsed.port == 17687
            and parsed.username is None and parsed.password is None and parsed.path in ('', '/')
            and not parsed.query and not parsed.fragment,
            'only the isolated loopback experiment URI is allowed')
    return GraphDatabase.driver(uri, auth=None, connection_timeout=3.0,
                                max_transaction_retry_time=3.0, max_connection_pool_size=4,
                                telemetry_disabled=True)


def components(driver):
    driver.verify_connectivity()
    with driver.session(database='neo4j') as session:
        row = session.run(Query('CALL dbms.components() YIELD versions, edition RETURN versions, edition',
                                timeout=2.0)).single().data()
    require(row['edition'] == 'community' and row['versions'][0].startswith('5.26.'), 'unexpected Neo4j edition/version')
    return row


def load_snapshot(driver, snapshot):
    """No deletes. Requires a dedicated empty/already-owned experiment DB."""
    with driver.session(database='neo4j') as session:
        row = session.run(Query('MATCH (n) WHERE n.namespace IS NULL OR NOT n.namespace IN $namespaces RETURN count(n) AS foreign',
                                timeout=2.0), namespaces=[snapshot.namespace,snapshot.namespace+':synthetic-test']).single()
        require(row['foreign'] == 0, 'refuse to load into a non-experiment database')
        @unit_of_work(timeout=5.0)
        def write(tx):
            for node in snapshot.nodes.values():
                tx.run('MERGE (n:RetrievalNode {namespace:$namespace, key:$key}) SET n=$properties',
                       namespace=snapshot.namespace,key=node['key'],properties=node).consume()
            queries = {
                'HAS_SOURCE':'MATCH (a:RetrievalNode {namespace:$ns,key:$a}), (b:RetrievalNode {namespace:$ns,key:$b}) MERGE (a)-[r:HAS_SOURCE]->(b) SET r.origin=$origin',
                'DESCRIBES':'MATCH (a:RetrievalNode {namespace:$ns,key:$a}), (b:RetrievalNode {namespace:$ns,key:$b}) MERGE (a)-[r:DESCRIBES]->(b) SET r.origin=$origin',
                'IN_REGION':'MATCH (a:RetrievalNode {namespace:$ns,key:$a}), (b:RetrievalNode {namespace:$ns,key:$b}) MERGE (a)-[r:IN_REGION]->(b) SET r.origin=$origin',
            }
            for edge in snapshot.edges:
                require(edge['type'] in ALLOWED_TYPES, 'unsupported loader relationship')
                tx.run(queries[edge['type']],ns=snapshot.namespace,a=edge['start'],b=edge['end'],origin=edge['origin']).consume()
        session.execute_write(write)


def verify_snapshot(driver, snapshot):
    real, local = Neo4jGraph(driver,snapshot), InProcessGraph(snapshot)
    tests=[]
    for key in sorted(snapshot.nodes):
        actual=real.expand((key,));expected=local.expand((key,))
        require(actual == expected,'Neo4j/in-process traversal mismatch')
        tests.append(dict(seed=key,ids=list(actual),matched=True))
    region=snapshot.aliases['region:seoul-jongno']
    require(real.expand((region,))==(OPTIONAL,), 'actual two-hop region relationship missing')
    document='document:'+OPTIONAL
    with driver.session(database='neo4j') as session:
        # Synthetic node/transport edge is in a separate namespace and never in the retrieval whitelist.
        session.run(Query('MATCH (d:RetrievalNode {namespace:$ns,key:$key}) MERGE (x:RetrievalNode {namespace:$other,key:$fake}) SET x.kind="document",x.path="records/weather/invented.json",x.origin="synthetic" MERGE (d)-[r:SYNTHETIC_TRANSPORT]->(x) SET r.origin="synthetic"',timeout=2.0),
                    ns=snapshot.namespace,key=document,other=snapshot.namespace+':synthetic-test',fake='synthetic:transport').consume()
    require(real.expand((region,))==(OPTIONAL,),'synthetic edge entered real retrieval')
    rejected=[]
    for field,bad in (('sha256','0'*64),('source_signatures',['unverified@revision@hash'])):
        update={'sha256':'MATCH (d:RetrievalNode {namespace:$ns,key:$key}) SET d.sha256=$value',
                'source_signatures':'MATCH (d:RetrievalNode {namespace:$ns,key:$key}) SET d.source_signatures=$value'}[field]
        original=snapshot.nodes[document][field]
        try:
            with driver.session(database='neo4j') as session:
                session.run(Query(update,timeout=2.0),ns=snapshot.namespace,key=document,value=bad).consume()
            try: real.expand((region,))
            except ValueError: rejected.append(field)
            else: raise ValueError('tampered real graph response accepted')
        finally:
            with driver.session(database='neo4j') as session:
                session.run(Query(update,timeout=2.0),ns=snapshot.namespace,key=document,value=original).consume()
    with driver.session(database='neo4j') as session:
        inventory=session.run(Query('MATCH (n:RetrievalNode {namespace:$ns}) OPTIONAL MATCH (n)-[r]->(m:RetrievalNode {namespace:$ns}) RETURN count(DISTINCT n) AS nodes,count(DISTINCT r) AS edges',timeout=2.0),ns=snapshot.namespace).single().data()
    require(inventory==dict(nodes=15,edges=22),'curated graph inventory drift')
    return dict(inventory=inventory,realSingletonQueries=len(tests),singletonChecks=tests,
                syntheticIsolationPassed=True,realTamperedResponseRejections=rejected,
                driverIntegration='actual server queries, not mocks',maxHops=2,maxDocuments=9)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--load',action='store_true')
    parser.add_argument('--uri',default=URI)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[3]
    snapshot=GraphSnapshot(Corpus(root,root.parent/'travel-context-wiki'))
    with network_scope(neo4j=True), driver_for(args.uri) as driver:
        server=components(driver)
        if args.load: load_snapshot(driver,snapshot)
        report=dict(server=server,uri=args.uri,namespace=snapshot.namespace,**verify_snapshot(driver,snapshot))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
