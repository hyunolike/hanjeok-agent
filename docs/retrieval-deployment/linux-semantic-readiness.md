# Linux CPU semantic verification and release prerequisites (2026-10-10)

The full **Linux ARM64 CPU** image actually ran a local pinned semantic model, a newly built immutable index, real Neo4j Community 5.26.31, HTTP and Kotlin citation/explanation paths. This closes the earlier unexecuted ARM64 semantic-image item; it does not prove Cloud Run deployment readiness. The runtime loader still rejects the old Mac torch pin. No production source, cloud IAM, credentials, resources, traffic, LLM/judge call or external corpus upload changed.

| Check | Actual result |
| --- | --- |
| Runtime | numpy 2.2.6, scikit-learn 1.7.2, Neo4j driver 5.26.0, sentence-transformers 6.1.0, transformers 5.19.0, **torch 2.14.1+cpu**; offline pip check passed |
| Fixed model | distiluse-base-multilingual-cased-v1 revision `826fee3d516ebb14987355af373f5b69101c7006`; all 13 model-file hashes identical to the preserved candidate; safetensors, local-only, no remote code |
| Actual encoding | 41 untruncated chunks, 512 dimensions, CPU; new matrix/index generated rather than relabelled |
| Old Mac index | `80dd5ab3b1ac4d73f74742ee880f2c5fdc04b2083079f19d17f07c37b00c95a5`, torch 2.14.1; preserved and rejected by Linux exact-pin loader |
| New Linux candidate | `8a2d47cf23a62d18ab97f85a72245376911f3a0fbe4c4d3e1e713f0f91461ef9`; independent final utility reproduces this identity |
| Image | `sha256:a9f48be025cc226d615dd328dcc342303d5e9d3fffbdf264fdb1b7d74f2bca64`, **linux/arm64**, 2,676,752,170 bytes |
| Candidate validation | 35 fixtures / 70 VECTOR+HYBRID rows, mandatory policies / evidence / bounds / unsupported queries; explicitly in-process graph validation |
| Actual graph | 15 curated nodes / 22 edges, same verified corpus namespace; synthetic isolation and tampered-response rejections; no invented transport/weather relationship |
| Real HYBRID API + Kotlin | 35 fixtures / 105 EXPLAIN/ASK/stream route checks / 35 determinism checks; 16 SELECTED, 14 FULL_FALLBACK, 5 ABSTAIN; actual normalized course facts EXPLAIN **SELECTED** |
| Real VECTOR API + Kotlin | 35 fixtures / 105 routes / 35 determinism checks; 14 SELECTED, 16 FULL_FALLBACK, 5 ABSTAIN; actual normalized course facts EXPLAIN **FULL_FALLBACK**, exact API reason `FALLBACK_REQUIRED_SEED` and original FULL bytes |
| Fault contracts | UID10001 / read-only normal API, hash-corrupt startup rejected, auth/schema/stale-pin bounds rejected, streamed body deadline 2.011s; graph corruption makes ready/retrieve 503 and Kotlin recovers exact FULL on all 3 routes; restoration returns 200 |
| Regression | Python API 19/19 and CPU builder 13/13; existing JVM 339/339 and lab 34/34 are separate from these fixture route counts |

The VECTOR facts guard demonstrates a seed omission, not retrieval quality improvement. The harness retains SELECTED as its default facts expectation; only explicit `VECTOR FALLBACK_REQUIRED_SEED` verifies this exact missing-seed response, its valid identity/schema/mode/array envelope and original FULL provider input. It also requires real SELECTED fixture rows, so an entirely unavailable API cannot pass. Unsupported fixtures abstain without scripted provider calls. The original lab's RAGAS 0.3.9 ID metrics remain preserved; **no new RAGAS or LLM-judge score is claimed for this Linux index**. Eight policies always remain; at most the 501-byte seed can be omitted (2.03% of 24,703 bytes). This is bounded source/declared-seed GraphRAG, not Microsoft's full community GraphRAG.

Evidence: [build](linux-semantic-build-proof.json), [final utility reproduction](linux-semantic-utility-reproduction.json), [candidate validation](linux-semantic-index-validation.json), [actual graph](linux-semantic-graph-proof.json), [HYBRID E2E](linux-semantic-hybrid-e2e.json), [VECTOR E2E](linux-semantic-vector-e2e.json), [facts fallback response](linux-semantic-vector-facts-response.json), [fault contracts](linux-semantic-image-contract.json), [wheel hashes](linux-semantic-wheel-manifest.json). [Protected source scope](linux-semantic-protected-scope-proof.json) confirms 52 operational agent files and 54 wiki evidence/index/package files unchanged. Local index/model/wheels are operator artifacts, not committed corpus copies or cloud uploads. [Owned cleanup proof](linux-semantic-cleanup-proof.json) confirms API/Bolt ports closed and task-labelled containers/images/graph/network removed; unrelated containers and shared model caches were preserved. Final JVM 339/339, wiki 8/8 smoke/18 canonical pages, unchanged static indexes and 182 README local targets pass.

## Reproduce the offline Linux CPU candidate

Start with the source-verified old candidate and fixed model already prepared by the native commands in [deployment instructions](../../deployment/retrieval/README.md). Supply platform-matching wheels from official PyPI and the [official PyTorch CPU wheel index](https://download.pytorch.org/whl/cpu/torch/). This experiment reused the existing model cache; it downloaded public wheels only. The new [Linux CPU requirement list](../../deployment/retrieval/requirements-semantic-linux-cpu.txt) pins all staged semantic dependencies in addition to the runtime list; retain the native list for native artifacts.

```sh
# Run from the repository. Preparation does not alter the old input.
export PYTHONPATH=retrieval-service:experiments/retrieval
PY=experiments/retrieval/.venv-semantic/bin/python
OLD=80dd5ab3b1ac4d73f74742ee880f2c5fdc04b2083079f19d17f07c37b00c95a5
# Replace OLD_INDEX, MODEL, BUILDER_CONTEXT and WHEELHOUSE with existing reviewed local paths.
$PY deployment/retrieval/prepare.py --index OLD_INDEX --version "$OLD" --model MODEL --destination BUILDER_CONTEXT
cp deployment/retrieval/requirements-semantic-linux-cpu.txt BUILDER_CONTEXT/requirements-semantic.txt
cp WHEELHOUSE/*.whl BUILDER_CONTEXT/wheelhouse/
# The base image and CPU wheels must match the requested platform; no implicit pull.
docker build --platform=linux/arm64 --network=none --pull=false --build-arg RETRIEVAL_BACKEND=semantic --label purpose=hanjeok-semantic-review -t hanjeok-retrieval-semantic:builder BUILDER_CONTEXT
# Names below must be unused. No host bind mount, key, .env or network access.
docker create --name semantic-candidate-review --label purpose=hanjeok-semantic-review --network none --memory 3g --cpus 2 --pids-limit 128 --entrypoint python hanjeok-retrieval-semantic:builder /tmp/rebuild-linux-cpu-index.py --input /app/index --destination /tmp/linux-candidate --version "$OLD" --model /app/model --fixtures /tmp/fixtures
```

Create an unused local `FIXTURE_STAGE` containing only the two public fixture files, preserving paths, and copy it into the stopped container. Then run:

```sh
mkdir -p FIXTURE_STAGE/harness/fixtures/context-selection FIXTURE_STAGE/experiments/retrieval/fixtures
cp harness/fixtures/context-selection/suite.json FIXTURE_STAGE/harness/fixtures/context-selection/
cp experiments/retrieval/fixtures/graph-cases.json FIXTURE_STAGE/experiments/retrieval/fixtures/
docker cp FIXTURE_STAGE semantic-candidate-review:/tmp/fixtures
docker cp deployment/retrieval/rebuild-linux-cpu-index.py semantic-candidate-review:/tmp/rebuild-linux-cpu-index.py
docker start -a semantic-candidate-review
docker cp semantic-candidate-review:/tmp/linux-candidate NEW_INDEX
# NEW_INDEX/manifest.json supplies the exact new version; never substitute the old version.
# Copy only the newly validated artifacts into the already reviewed context; preserve model/wheels.
cp -R NEW_INDEX/. BUILDER_CONTEXT/index/
docker build --platform=linux/arm64 --network=none --pull=false --build-arg RETRIEVAL_BACKEND=semantic --label purpose=hanjeok-semantic-review -t hanjeok-retrieval-semantic:validated BUILDER_CONTEXT
sh experiments/retrieval/scripts/neo4j-local.sh start
# Host cannot load Linux runtime pins in its Mac Python. Only load the old, source-verified
# native graph after proving graph bytes are identical; graph identity is independent of vectors.
cmp OLD_INDEX/graph.json NEW_INDEX/graph.json
$PY deployment/retrieval/local-api-smoke.py --index OLD_INDEX --version "$OLD" --output /tmp/graph-load.json --load-owned-graph --load-only
VERSION="$($PY -c 'import json; print(json.load(open("NEW_INDEX/manifest.json"))["indexVersion"])')"
SUBNET="$(docker network inspect hanjeok-retrieval-task8-net --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}')"
docker run --pull=never -d --name semantic-api-review --label purpose=hanjeok-semantic-review --network hanjeok-retrieval-task8-net --memory 2g --cpus 2 --pids-limit 128 --read-only --cap-drop=ALL --security-opt no-new-privileges=true --tmpfs /tmp:rw,noexec,nosuid,size=64m -p 127.0.0.1:17883:8080 -e RETRIEVAL_AUTH_MODE=isolated-container-test -e RETRIEVAL_LOCAL_CONTAINER_TEST=1 -e RETRIEVAL_TEST_NETWORK="$SUBNET" -e RETRIEVAL_LOCAL_TOKEN=local-test -e RETRIEVAL_INDEX_VERSION="$VERSION" -e RETRIEVAL_GRAPH_MODE=neo4j -e RETRIEVAL_NEO4J_URI=bolt://hanjeok-retrieval-task8:7687 hanjeok-retrieval-semantic:validated
# Wait for authenticated readiness before running the Kotlin checks. No paid provider runs.
./gradlew --offline --no-daemon retrievalServiceE2e --args='NEW_INDEX http://127.0.0.1:17883 hybrid.json HYBRID_GRAPH'
# Stop/remove only semantic-api-review after confirming its purpose label, then restart the same command
# with RETRIEVAL_GRAPH_MODE=disabled on the same loopback port. When the real response has this exact expected seed miss:
./gradlew --offline --no-daemon retrievalServiceE2e --args='NEW_INDEX http://127.0.0.1:17883 vector.json VECTOR FALLBACK_REQUIRED_SEED'
$PY deployment/retrieval/test_rebuild_cpu_index.py
```

Keep available disk above 8GiB and builder memory at 3GiB. Observed host disk was 12–15GiB free; Docker VM 7.67GiB/4CPU, existing unrelated services ≈220MiB. API/Neo4j observed 477MiB/571MiB with respective 2GiB limits; this is a local snapshot, not production sizing or latency certification. Cleanup only containers/images bearing this task's purpose label; remove the owned API first, then the owned graph/network. Never prune unrelated images, databases, shared caches or model files.

## Existing cloud configuration and exact approval prerequisites

[Read-only inspection](cloud-readonly-inspection.json) found project `hanjeok-prod`, region `asia-northeast3`, current `hermes-agent-ea47917-b64ed4cc2` Ready at 100% traffic. The agent has no retrieval mode/endpoint, so it retains FULL. Existing runtime identity is `508380543987-compute@developer.gserviceaccount.com`, with existing project-level `roles/editor` (not newly granted). This is broad and is not a least-privilege certificate. Artifact Registry repositories `hermes` and `hanjeok`, VPC `hanjeok-vpc`, subnet `hanjeok-subnet` (10.10.0.0/24) exist; Private Google Access is false and the current agent has no VPC egress configuration. No existing retrieval service or Neo4j reader endpoint/secret was located in the inspected scope. Secret values were not read, and no actual production Neo4j ACL test was possible.

1. **Architecture before any upload:** validate a fresh **linux/amd64** CPU index and final image in the matching runtime. The [interrupted amd64 builder](amd64-semantic-recovery.md) confirms build, x86_64 Python, pip check and weight loading only; it retains the old Mac index and is not deployable. Cloud Run requires x86_64 or a multi-arch manifest including amd64; this tested ARM64 image cannot be promoted as-is. This comes from the [Cloud Run container contract](https://docs.cloud.google.com/run/docs/container-contract), not an assumption that any Linux image is deployable.
2. **Resolve the existing graph target:** obtain the actual TLS URI, database, existing reader user and existing Secret Manager secret/version. Current startup accepts Enterprise `reader` plus PUBLIC only, and hard-codes the `neo4j` graph database; a custom limited role or different database requires separately reviewed code. The built-in reader reads all data graphs, so the minimum no-code choice is an existing dedicated retrieval database/server and verified reader-only identity. Broader shared databases need a narrower reviewed role/database adapter before approval. Inspect effective privileges (including PUBLIC/custom grants) and perform approved write-denial checks; local Community/READ_ACCESS does not prove ACL. [Neo4j roles](https://neo4j.com/docs/operations-manual/current/authentication-authorization/built-in-roles/).
3. **Review new resource and IAM targets:** proposed new service `hanjeok-prod/asia-northeast3/hanjeok-retrieval`, image in existing `hermes` registry. Give only current caller SA `roles/run.invoker` **on that new service**, no allUsers/allAuthenticatedUsers. Runtime retrieval SA must be a resolved existing approved identity with `roles/secretmanager.secretAccessor` only on the actual resolved reader secret; new SA/secret creation would be a separate explicit approval. Google-signed ID-token audience must equal its Cloud Run service URL. [Service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).
4. **Review the network path:** internal ingress requires agent-to-retrieval traffic through VPC, not simply the same project. Proposed target is existing `hanjeok-vpc/hanjeok-subnet`, enabling Private Google Access and configuring source Direct VPC egress plus reviewed private DNS for run.app/private.googleapis.com. The alternate all-traffic route changes all backend/LLM egress and may need NAT; do not apply it without inspecting those destinations and cost. No connector/NAT/DNS resource was provisioned. [Private networking](https://docs.cloud.google.com/run/docs/securing/private-networking).
5. **Cost review, then private validation:** initial review envelope 2vCPU/2GiB, concurrency 1, min 0/max 1. Request-based compute is billed vCPU/GiB-seconds plus requests; use the Seoul rates, actual billed active/startup duration and remaining shared free tier. Budget formula is `2×billedSeconds×SeoulCPUPrice + 2×billedSeconds×SeoulMemoryPrice + request/storage/network charges`. Registry storage, DNS/connector/NAT if selected, Neo4j existing license/hosting and external networking are separate. No workload or existing graph cost is known, so no defensible monthly total is given. This local test created no cloud resource charge. [Current Cloud Run pricing](https://cloud.google.com/run/pricing).
6. Only after those targets/costs are approved: stage a private retrieval revision; confirm unauthenticated/wrong-audience denial, exact authenticated readiness/provenance and graph read/write boundaries. Keep agent FULL while validating a separate selected-mode candidate. Agent image publication, serving traffic and separate Hanjeok DB/SMTP deployment each remain separate decisions.

Agent PR14/wiki PR33 were externally merged at 2026-10-10 04:32:58/04:33:26UTC; their successful exact-head CI is historical evidence, not a production retrieval rollout. Original follow-up commits `94e5daa` / `8dfa9b1` are preserved. Separate feature branches based on the latest main contain only subsequent changes and the interrupted-amd64 record for new Draft PR review. Historical verification snapshots retain their original publication/architecture flags. Existing useful 3D figures are restored, duplicate diagrams/statistics/stack decorations removed, and the attached JPEG was identified as the old collection-stats card through official Library materialization and pixel inspection. Counts remain in a plain table; no new image generation or asset replacement is claimed.
