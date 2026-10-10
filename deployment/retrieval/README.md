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

`release-plan.sh check` and `release-plan.sh rollback` print review steps only. Cloud Run YAML/environment files are templates with placeholders, not a deployment. Private IAM must be enforced by the platform before requests reach the ASGI app; the app's Bearer presence check is **not** JWT verification. Kotlin can request an ID token from the existing attached identity; no credential or IAM is created. Actual cloud IAM/private networking/invoker policy and Linux image builds remain unexecuted.

HYBRID_GRAPH runtime requires a real TLS Neo4j graph with the exact pinned curated snapshot. Production additionally requires an existing Enterprise reader-only role, checked at startup; driver READ_ACCESS is not an ACL. The role contract is mocked locally. Earlier lab results used real isolated Neo4j Community queries and verified two-hop/nine-document/source-hash boundaries; that does not validate production reader privileges. New API E2E has graph disabled; hybrid candidate validation uses the explicitly labelled in-process contract. No transport/weather/synthetic relation is imported into runtime search.

Existing production/default FULL, paid providers, existing deployment, main branches and Draft PR heads are unchanged by this local follow-up. No follow-up push, cloud resource, credentials, IAM change, deployment or traffic publication has occurred. See `docs/retrieval-deployment/verification.json` for actual checks and remaining approval prerequisites.
