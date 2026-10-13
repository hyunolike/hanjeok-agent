#!/bin/sh
# Explicit opt-in helper. No pulls, credentials, host mounts or production services.
set -eu
name=hanjeok-retrieval-task8
network=hanjeok-retrieval-task8-net
purpose=hanjeok-retrieval-task8
image=neo4j@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93
owned_container() {
    test "$(docker inspect --format '{{index .Config.Labels "purpose"}}' "$name")" = "$purpose"
}
owned_network() {
    test "$(docker network inspect --format '{{index .Labels "purpose"}}' "$network")" = "$purpose"
    test "$(docker network inspect --format '{{index .Options "com.docker.network.bridge.enable_ip_masquerade"}}' "$network")" = false
}
case "${1:-status}" in
start)
    if docker inspect "$name" >/dev/null 2>&1; then
        echo 'Container name already exists; inspect it before starting.' >&2; exit 1
    fi
    docker image inspect "$image" >/dev/null
    if docker network inspect "$network" >/dev/null 2>&1; then
        owned_network
    else
        docker network create --opt com.docker.network.bridge.enable_ip_masquerade=false --label "purpose=$purpose" "$network" >/dev/null
    fi
    docker run --pull=never -d --name "$name" --label "purpose=$purpose" \
      --network "$network" --memory 2g --cpus 2 --restart=no \
      -p 127.0.0.1:17687:7687 -e NEO4J_AUTH=none \
      -e NEO4J_dbms_usage__report_enabled=false -e NEO4J_server_http_enabled=false \
      -e NEO4J_server_memory_heap_initial__size=256m -e NEO4J_server_memory_heap_max__size=512m \
      -e NEO4J_server_memory_pagecache_size=128m "$image"
    echo 'Wait for Bolt ready in: docker logs --tail 24 hanjeok-retrieval-task8'
    ;;
stop)
    if docker inspect "$name" >/dev/null 2>&1; then
        owned_container
        docker stop --time 10 "$name" >/dev/null
        docker rm -v "$name" >/dev/null
    fi
    if docker network inspect "$network" >/dev/null 2>&1; then
        owned_network
        docker network rm "$network" >/dev/null
    fi
    echo 'Only the labelled experiment container, anonymous volumes and dedicated network removed.'
    ;;
status)
    owned_container
    docker inspect --format '{{json .State}}' "$name"
    docker logs --tail 24 "$name"
    ;;
*) echo 'usage: neo4j-local.sh start|status|stop' >&2; exit 2 ;;
esac
