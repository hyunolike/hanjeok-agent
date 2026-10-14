# Sourced by build-graph.sh and start.sh: start the container's own Neo4j and
# wait until it answers.
#
# Neo4j listens inside the container only. Its password is made once, when the
# image is built, and kept beside the data it protects; it guards nothing that
# is reachable from outside.

GRAPH_HOME=${GRAPH_HOME:-/app/graph}

start_neo4j() {
  mkdir -p "$GRAPH_HOME/data" "$GRAPH_HOME/logs" "$GRAPH_HOME/run"
  if [ ! -f "$GRAPH_HOME/password" ]; then
    head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24 >"$GRAPH_HOME/password"
  fi
  local password
  password=$(cat "$GRAPH_HOME/password")
  export BENCH_NEO4J_URI=bolt://127.0.0.1:7687 BENCH_NEO4J_USER=neo4j BENCH_NEO4J_PASSWORD="$password"
  export NEO4J_AUTH="neo4j/$password" \
    NEO4J_server_directories_data="$GRAPH_HOME/data" \
    NEO4J_server_directories_logs="$GRAPH_HOME/logs" \
    NEO4J_server_directories_run="$GRAPH_HOME/run" \
    NEO4J_server_default__listen__address=127.0.0.1 \
    NEO4J_server_memory_heap_initial__size=512m \
    NEO4J_server_memory_heap_max__size=1G \
    NEO4J_server_memory_pagecache_size=512m \
    NEO4J_server_jvm_additional="--add-modules jdk.incubator.vector"

  /startup/docker-entrypoint.sh neo4j >"$GRAPH_HOME/logs/console.log" 2>&1 &
  NEO4J_PID=$!

  for _ in $(seq 1 180); do
    if cypher-shell -a "$BENCH_NEO4J_URI" -u neo4j -p "$password" "RETURN 1" >/dev/null 2>&1; then
      return 0
    fi
    if ! kill -0 "$NEO4J_PID" 2>/dev/null; then
      echo "Neo4j exited while starting:" >&2
      tail -n 40 "$GRAPH_HOME/logs/console.log" >&2
      return 1
    fi
    sleep 1
  done
  echo "Neo4j did not answer within three minutes." >&2
  tail -n 40 "$GRAPH_HOME/logs/console.log" >&2
  return 1
}
