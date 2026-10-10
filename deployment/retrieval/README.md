# Private retrieval release preparation (local branch only)

This opt-in API is separate from production FULL. It returns pinned IDs/hashes, never document text or query logs. Kotlin resolves those IDs against its packaged verified bundle, keeps all eight policies, supplies optional seed JSON as untrusted user data, and owns citations, repair, cache identity and verified FULL fallback. Source integrity does not prove semantic truth or completed review. Corpus selection still has only one optional 501-byte seed, about 2.03% of the 24,703-byte FULL bundle; moving evidence to user input and adding guards does not imply total token/cost savings.

TF-IDF is lexical retrieval. The CPU multilingual semantic adapter uses a separately packaged, hash-checked local model at revision `826fee3d516ebb14987355af373f5b69101c7006`, with no runtime download or remote model code. RAGAS/judges are evaluation-only, excluded from service dependencies. This is bounded source/seed graph retrieval, not the full Microsoft community GraphRAG system.

## Reproduce locally

Use the preserved Python 3.12 semantic environment (or an equivalent pinned runtime), from the agent repository root:

```sh
export PYTHONPATH=retrieval-service:experiments/retrieval
PY=experiments/retrieval/.venv-semantic/bin/python
$PY -m unittest discover -s retrieval-service/tests -v
$PY -m retrieval_service.cli build --agent . --wiki ../travel-context-wiki --destination /tmp/retrieval-candidate --backend tfidf
# Semantic: add --backend semantic --model-path experiments/retrieval/models/distiluse-base-multilingual-cased-v1
# Copy the printed hash into VERSION (never infer latest at runtime).
VERSION=VALIDATED_MANIFEST_HASH
$PY -m retrieval_service.cli validate --agent . --directory /tmp/retrieval-candidate --version "$VERSION"
# Semantic validation also needs --model-path, as above.
$PY -m retrieval_service.cli publish --directory /tmp/retrieval-candidate --version "$VERSION" --registry /tmp/retrieval-registry.json
$PY -m retrieval_service.cli rollback --registry /tmp/retrieval-registry.json --version "$VERSION"
```

Publication only updates a local atomic registry, retains validated pairs, and never hot-reloads a running service or switches cloud traffic. A trusted operator must validate the original 29 and six graph cases (70 rows), keep index/model/bundle/sidecar/graph namespace compatible, stage an immutable artifact, and review its version. Reports are integrity records, not signed independent attestations.

For local HTTP, install pinned Uvicorn runtime dependencies into a separate environment/target directory; no RAGAS or LLM provider is needed. Set `RETRIEVAL_AUTH_MODE=loopback-test`, `RETRIEVAL_BIND=127.0.0.1`, `RETRIEVAL_LOCAL_TOKEN=local-test`, explicit index directory/version, optional verified model directory, `RETRIEVAL_GRAPH_MODE=disabled`, `PORT=17780`, then run `$PY -m retrieval_service.runtime`. Local auth is prohibited when `K_SERVICE` is present.

```sh
./gradlew --offline --no-daemon retrievalServiceE2e --args='/tmp/retrieval-candidate http://127.0.0.1:17780 /tmp/retrieval-e2e.json'
./gradlew --offline --no-daemon test bootJar offlineContextEval
```

The E2E uses real HTTP/vector retrieval plus actual Kotlin explanation/ask/stream citation gates with a scripted provider. It checks 35 fixtures, determinism, all policies, required coverage, unsupported abstention and stale-pin FULL recovery. It does not measure answer quality or invoke an LLM judge. API admission is one in-flight operation with bounded request/response/deadline; timed-out work retains its slot until it finishes. Readiness uses the same bounded worker. `/agent/retrieval-status` exposes only aggregate pins/counters; authenticated Python `/health/ready` and `/v1/provenance` recheck artifact integrity. Liveness is not readiness.

## Prepare, inspect, roll back

`prepare.py --index ... --version ... --destination ... [--model ...]` stages a verified, validated image context, excluding credentials and evaluation fixtures. Supply approved, platform-matching pinned CPU wheels in its empty `wheelhouse/`, review/pin the Python base digest, and build only after approval. Docker uses non-root UID 10001 and read-only artifact permissions. Runtime never writes or rebuilds an index. Semantic build uses `--build-arg RETRIEVAL_BACKEND=semantic`.

`release-plan.sh check` and `release-plan.sh rollback` print review steps only. Cloud Run YAML/environment files are templates with placeholders, not a deployment. Private IAM must be enforced by the platform before requests reach the ASGI app; the app's Bearer presence check is **not** JWT verification. Kotlin can request an ID token from the existing attached identity; no credential or IAM is created. Actual cloud IAM/private networking/invoker policy remains unexecuted. Linux ARM64 lexical image is now built and tested locally.

HYBRID_GRAPH runtime requires a real TLS Neo4j graph with the exact pinned curated snapshot. Production additionally requires an existing Enterprise reader-only role, checked at startup; driver READ_ACCESS is not an ACL. The role contract is mocked locally. Earlier lab results used real isolated Neo4j Community queries and verified two-hop/nine-document/source-hash boundaries; that does not validate production reader privileges. Original 915c91d API E2E had graph disabled; subsequent actual API-to-Neo4j E2E runs are recorded below. Hybrid candidate validation still uses its explicitly labelled in-process contract. No transport/weather/synthetic relation is imported into runtime search.

Existing production/default FULL, paid providers, existing deployment, main branches and previous PR heads are unchanged by this local follow-up. No follow-up push, cloud resource, credentials, IAM change, deployment or traffic publication has occurred. See `docs/retrieval-deployment/verification.json` for actual checks and remaining approval prerequisites.

## Actual local gap closure (2026-10-10)

See [verification](../../docs/retrieval-deployment/verification.json), preserved [915c91d snapshot](../../docs/retrieval-deployment/verification-at-915c91d.json), [Linux image contract](../../docs/retrieval-deployment/linux-image-contract-smoke.json) and [real graph proof](../../docs/retrieval-deployment/new-api-graph-proof.json). Python 19/19 and JVM 339/339 pass. The overlapping selected/FULL cache and real fixture-facts EXPLAIN gaps are closed. Real Neo4j Community 5.26.31 is used through native lexical/semantic APIs and the Linux ARM64 lexical image: each verifies 35 fixtures/105 service routes plus actual fixture facts EXPLAIN. All providers are scripted; no answer-quality/judge claim.

The final lexical image uses non-root UID10001, immutable artifact permissions, readonly root filesystem, an offline pinned wheelhouse and digest-pinned Python base. Actual 2s streamed-body timeout, auth/schema/size/version rejection, provenance pins, hash-corrupt startup rejection and graph-corrupt readiness DOWN/Kotlin FULL recovery pass. Production IAM and Enterprise reader permissions are still not verified locally. The full Linux semantic image remains held: the official CPU distribution is `torch 2.14.1+cpu`, while the preserved candidate pins `2.14.1`; build a new validated Linux CPU candidate instead of silently changing the pin. See the [official CPU wheel index](https://download.pytorch.org/whl/cpu/torch/).

`isolated-container-test` is an explicit local Docker profile: exact test token plus a narrow RFC1918 network, `RETRIEVAL_LOCAL_CONTAINER_TEST=1`, bind 0.0.0.0, and no K_SERVICE. It is refused on Cloud Run. Use only a labelled private fixture bridge with masquerading disabled and publish API/Bolt to host 127.0.0.1. The allowed graph alias is only `bolt://hanjeok-retrieval-task8:7687`. It does not prove cloud IAM or graph ACL.

```sh
# Build the context prepared earlier, with platform-matching wheels already staged.
docker build --network=none --pull=false --label purpose=hanjeok-retrieval-api-task8 -t hanjeok-retrieval-api:local-smoke PREPARED_CONTEXT
sh experiments/retrieval/scripts/neo4j-local.sh start
# Load the immutable index snapshot into the owned empty fixture DB before starting API.
$PY deployment/retrieval/local-api-smoke.py --index INDEX_DIR --version "$VERSION" --output /tmp/graph-load.json --load-owned-graph --load-only
# Set SUBNET from docker network inspect hanjeok-retrieval-task8-net (not a public range).
# Start image with RETRIEVAL_AUTH_MODE=isolated-container-test, explicit marker/subnet/token/index-version,
# RETRIEVAL_GRAPH_MODE=neo4j, allowed graph URI, --network hanjeok-retrieval-task8-net,
# --read-only --cap-drop=ALL --security-opt no-new-privileges=true, and -p 127.0.0.1:17880:8080.
$PY deployment/retrieval/local-api-smoke.py --index INDEX_DIR --version "$VERSION" --origin http://127.0.0.1:17880 --output /tmp/api-smoke.json --fault-owned-graph
./gradlew --offline --no-daemon retrievalServiceE2e --args='INDEX_DIR http://127.0.0.1:17880 /tmp/graph-e2e.json HYBRID_GRAPH'
# During an explicitly injected graph outage/corruption:
./gradlew --offline --no-daemon retrievalRecoverySmoke --args='INDEX_DIR http://127.0.0.1:17880 /tmp/recovery.json'
# Remove only your labelled API container first, then stop the owned Neo4j helper.
sh experiments/retrieval/scripts/neo4j-local.sh stop
```

The host bind-mount negative test stalled before container creation, so the actual negative startup test used `docker create` + `docker cp` into its own stopped container layer. Normal runtime has no host bind mount. Default public fetch also waited on Docker Desktop's credential helper; an isolated anonymous client resolved it without user credential changes. These are local tooling observations, not cloud verification.

The graph-only `--load-only` command explicitly records `actualHttp: false`; it is not an API startup/HTTP proof. The corresponding regression is part of Python 19/19. Final review and [owned cleanup proof](../../docs/retrieval-deployment/cleanup-proof.json) are recorded separately from cloud prerequisites.
