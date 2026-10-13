# Retrieval deployment-readiness follow-up (2026-10-10)

Status: design proposal grounded in current repositories; no product implementation, paid resource, account/credential/permission change, deployment or traffic switch performed. This scope is separate from agent Draft #13 / wiki Draft #32. Current production is FULL.

## Recommended boundary

Keep Kotlin/Spring as the public agent and the authority for mandatory policy, prompt assembly, response citations and safe fallback. Package Python retrieval as a separate private HTTP service, reusing the tested lexical, pinned semantic and fixed Neo4j adapters. Do not put Python/PyTorch or RAGAS/judge execution in the current JVM production image. This avoids replacing Spring or rewriting the actually executed semantic pipeline into an unverified Kotlin approximation.

Alternatives: (1) a Kotlin-only lexical retriever has lower deployment overhead but would omit the tested semantic implementation; (2) a Python subprocess in the existing container couples model memory/lifecycle to the agent and increases image/runtime risk. A separate service adds network/authentication and potential compute cost; implement/configure it locally first, with actual Cloud Run provisioning held.

## Agent behavior

`FULL` remains the default and preserves current system/user bytes and request behavior. Explicit VECTOR/HYBRID_GRAPH configuration enables the new client; a request cannot enable it. The agent first loads/verifies the packaged FULL body/sidecar. If that baseline is corrupt, startup/readiness fails closed; remote search must never repair it.

In selected modes, retain all eight mandatory policy documents in declared order. Resolve returned document IDs against the agent's pinned local corpus and verify document/source hashes and revisions. Returned evidence remains a separately labelled untrusted user-data block; do not append remote instructions to system policy. Do not accept arbitrary text, URL paths, Cypher, namespace or graph edge types from a request. Reject unknown/duplicate IDs, oversize/non-finite scores and incomplete version metadata. Restrict citations to policy plus actually selected evidence. Search failure, timeout, authentication failure, graph outage or version mismatch returns the verified original FULL request context and its citation boundary.

Apply this boundary to EXPLAIN, blocking ASK and streaming ASK without changing ranking/tools. Include selected-context/index identity in explanation-cache and single-flight keys so a cache hit cannot reuse an answer for a different context. Preserve facts-first cache, completion-based TTL, citation-before-delta stream and existing 2-tool-round/60-second loop budget. Preserve client-owned history.

## Private API and limits

Proposed endpoints: POST `/v1/retrieve`, GET `/health/live`, GET `/health/ready`, authenticated GET `/v1/provenance`. Contract version 1 request includes bounded query, requested supported mode and expected corpus/index/model fingerprints. Response includes actual fingerprints, selection/fallback/abstain status, ordered candidate document IDs/scores and source signatures. The response is retrieval metadata, not an answer.

Initial hard caps: request 8 KiB, query 1,024 characters and 4 KiB UTF-8 (semantic token-window overflow rejected), response 64 KiB, top-k 3, max returned documents 9 and graph max 2 hops. Start with one in-flight retrieval per Python process, bounded admission with 429 on overflow, no unbounded queue, no query/facts/body logging. Agent connect timeout 500 ms, total retrieval budget 2 s, response bytes bounded while reading; no network retry inside a user request. No redirects and only configured HTTPS service origin outside loopback-local mode. Graph transaction deadline remains 2 s and is limited by the caller's total budget.

Authentication: deploy a private Cloud Run service and attach a short-lived audience-bound ID token from the agent service identity, with token acquisition behind an injectable provider for local contract tests. Cloud Run validates the identity and requires invoker permission. Local tests use explicit loopback-only test authentication. Do not create a key file or commit a token; actual service account/IAM configuration remains a separate approval step. Authentication is a deployment precondition, not a claim established by local mocks.

## Immutable index and publication

Build candidate indexes offline from verified Git sources and the exact packaged bundle/sidecar. Persist only safe deterministic JSON/NPZ arrays (no pickle), corpus hashes, declared source revisions, lexical algorithm/version or pinned semantic model revision/artifact hashes/dimension/chunking, matrix hash and graph snapshot namespace/allowlist. Runtime loads an exact expected manifest fingerprint and immutable candidate directory; no Git clone/model download/automatic source refresh.

Stages: build candidate → verify inventory/hashes/schema → run original 29 plus 6 boundary fixtures and API/citation checks → locally mark candidate publishable → build versioned image/config → separately approved private deployment with no production traffic → authenticated readiness/provenance check → separately approved traffic/config switch. Keep previous image digest, index/corpus fingerprint and graph namespace; rollback selects the previous pair. Publishing raw or canonical updates must never mutate a running index automatically.

Cloud Run's writable filesystem is ephemeral, so do not use it as durable publication storage. Embed the validated index and optionally the verified local model in the retrieval image for this initial design; deploy new immutable revisions for changes. Prepare max-instances/concurrency/startup probes/resource examples without applying them. Semantic CPU resource sizing still requires local RSS/startup/inference measurements; no performance SLA has yet been demonstrated.

## Neo4j boundary and approval prerequisite

Reuse the fixed, parameterized read Cypher and exact node/edge namespace allowlists, maximum 2 hops/9 docs, actual row hash/source signature checks and deterministic ordering. Curated relations are only HAS_SOURCE, DESCRIBES and IN_REGION; synthetic namespaces remain isolated. The runtime API has no graph-write/publish endpoint. Offline graph publisher uses a separate operator credential and never shares it with the API.

Neo4j READ_ACCESS is driver routing, not access control. The already tested Community 5.26.31 container does not establish a production reader-role permission contract. Production HYBRID_GRAPH requires an existing Neo4j deployment capable of enforcing read-only runtime access, or a separately approved read-only deployment plan. RBAC is an Enterprise capability in official Neo4j documentation. Do not pretend an admin/community credential is read-only; prepare the permission/config check and fail readiness if the selected production graph cannot satisfy it. No Enterprise/Aura subscription, database hosting or reader account is created here.

## Deliverables and verification

Follow-up branch candidate: agent retrieval service/API schema and client boundary; immutable index builder/validator and publish/rollback tooling; isolated Dockerfile and deployment/config/environment examples; readiness/provenance and sanitized fallback counters; targeted Kotlin/Python contracts; local end-to-end provider stub with API, pinned ID validation, mandatory policy, prompt separation and real citation gate. Wiki only needs a distinct deployment-readiness status link after implementation.

Verify FULL default makes no retrieval request; source corruption fails closed; all 8 policies remain; semantic VECTOR's known seed omissions stay visible; unsupported questions/relations never produce invented weather/transport facts; outage/auth/version/response-boundary failures use verified FULL; concurrent/oversize/time-limit failures stay bounded; model/corpus/index mismatch blocks readiness; publication is manual and rollback restores a compatible pair. Use actual existing Neo4j/semantic results as prior evidence and run additional local integration only within approved infrastructure constraints. LLM generation/judging remains scripted/not run.

Before any follow-up push, report exact changed files and local test results as requested. No follow-up remote push is performed in this design phase. Before real deployment, request concrete approval for new Cloud Run compute, IAM/service identity/credential operations and any Neo4j hosting/licensing requirement. Minimum deployment option is VECTOR without a new Neo4j resource; FULL remains available independently.

Sources:
- Current code: BundleLoader, PromptAssembler, ExplanationService, CourseQuestionService, ExplanationCache, ContextController, retrieval_lab/corpus.py, vector.py and neo4j_adapter.py.
- https://docs.cloud.google.com/run/docs/authenticating/service-to-service
- https://docs.cloud.google.com/run/docs/container-contract
- https://neo4j.com/docs/operations-manual/current/authentication-authorization/
- https://neo4j.com/docs/operations-manual/current/introduction/
