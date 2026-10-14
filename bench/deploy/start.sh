#!/usr/bin/env bash
# Start the Neo4j whose graph was built into the image, then serve.
#
# The server is not started until Neo4j answers, so the port opens only when a
# question could actually be answered.
set -euo pipefail

: "${PORT:=7860}"
if [ "${GUIDE_ENV:-}" = "production" ] && [ -z "${GUIDE_CORS_ALLOWED_ORIGINS:-}" ]; then
  echo "GUIDE_CORS_ALLOWED_ORIGINS is required (the site that may call this service)." >&2
  exit 1
fi

. /app/deploy/neo4j.sh
echo "starting Neo4j…"
start_neo4j

cd /app/bench
echo "serving on :$PORT"
exec uvicorn guide.api:app --host 0.0.0.0 --port "$PORT"
