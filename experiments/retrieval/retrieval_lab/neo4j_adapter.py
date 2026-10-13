"""Fixed bounded read-only Neo4j query; mock and actual execution tracked separately."""
from neo4j import READ_ACCESS, unit_of_work
from .corpus import require

READ_CYPHER = '''
MATCH p=(start:RetrievalNode)-[:HAS_SOURCE|DESCRIBES|IN_REGION*0..2]-(d:RetrievalNode)
WHERE start.namespace = $namespace AND start.key IN $seed_keys
  AND d.kind = 'document' AND d.namespace = $namespace
  AND all(n IN nodes(p) WHERE n.namespace = $namespace AND n.key IN $allowed_keys)
  AND all(r IN relationships(p) WHERE r.origin IN ['verified_sidecar', 'seed_fixture']
      AND (startNode(r).key + '|' + type(r) + '|' + endNode(r).key + '|' + r.origin) IN $allowed_edges)
RETURN DISTINCT d.key AS key, d.path AS path, d.sha256 AS sha256,
                d.namespace AS namespace, d.source_signatures AS source_signatures
ORDER BY path
LIMIT $limit
'''


class Neo4jGraph:
    status = 'actual Neo4j driver; execution provenance recorded by caller'

    def __init__(self, driver, snapshot, database='neo4j'):
        self.driver, self.snapshot, self.database = driver, snapshot, database

    def expand(self, keys, limit=9):
        self.snapshot.validate_request(keys, limit)
        parameters = dict(namespace=self.snapshot.namespace, seed_keys=list(keys),
                          allowed_keys=sorted(self.snapshot.nodes), allowed_edges=sorted(self.snapshot.allowed_edges), limit=limit)
        @unit_of_work(timeout=2.0)
        def read(tx):
            return [record.data() for record in tx.run(READ_CYPHER, parameters)]
        # READ_ACCESS is routing, not an ACL. Fixed query + verified rows enforce this contract.
        with self.driver.session(database=self.database, default_access_mode=READ_ACCESS) as session:
            rows = session.execute_read(read)
        require(len(rows) <= limit, 'unbounded graph response')
        paths = tuple(self.snapshot.validate_row(row) for row in rows)
        require(len(set(paths)) == len(paths), 'duplicate graph response')
        return tuple(sorted(paths))
