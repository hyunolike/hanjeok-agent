#!/usr/bin/env bash
# Run while the image is built: load the wiki and the export into Neo4j, then
# stop it cleanly so the image carries a finished graph.
#
# Why here and not at start: a Cloud Run instance that wakes from zero would
# otherwise spend its first minutes writing thirteen thousand places before it
# could answer anything. With the graph already in the image, waking is
# starting Neo4j and nothing else.
#
# The graph is still derived and disposable. It is rebuilt from the export and
# the wiki by rebuilding the image; nothing is ever written to it that is not
# in those two.
set -euo pipefail
. /app/deploy/neo4j.sh

start_neo4j
cd /app/bench
echo "loading the policy wiki…"
bench corpus load wiki
echo "loading places…"
guide refresh --export /app/data/export --cache /app/data/embeddings.sqlite

# A clean stop, so the store needs no recovery when the container starts.
kill -TERM "$NEO4J_PID"
wait "$NEO4J_PID" 2>/dev/null || true
rm -rf "$GRAPH_HOME/run" "$GRAPH_HOME/logs"
echo "graph built: $(du -sh "$GRAPH_HOME/data" | cut -f1)"
