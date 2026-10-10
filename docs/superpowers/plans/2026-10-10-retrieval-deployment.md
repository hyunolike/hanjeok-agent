# Retrieval Deployment Readiness Implementation Plan

> For agentic workers: execute natively with superpowers:executing-plans; user approved this boundary and local implementation. No follow-up push or cloud mutation.

Goal: provide a runnable private retrieval service and an opt-in Kotlin request boundary with immutable, manually published indexes, verified FULL fallback and local API-to-citation tests.
Architecture: reuse existing verified Python search/graph adapters behind a small ASGI HTTP application served by Uvicorn. Kotlin owns policy, local evidence resolution and citations. Runtime never clones Git, downloads a model, updates an index or executes RAGAS/judge.
Tech Stack: existing Python 3.12, numpy/scikit-learn/Neo4j driver and pinned sentence-transformer; Uvicorn 0.54.0; existing Kotlin/JDK21/Spring and JDK HttpClient.
Spec: ../specs/2026-10-10-retrieval-deployment-design.md

## Global constraints

FULL defaults and exact default system/user bytes remain unchanged. Preserve all 8 policies and 29 original plus 6 graph fixtures. 2-hop/9-document graph cap, source hash/revision integrity, no synthetic/weather/transport invention, no external paid model/judge calls. New code remains local on a distinct branch. Credentials, IAM, actual cloud infrastructure/deployment and production traffic require separate approval. Driver READ_ACCESS is not an ACL.

## Review focus

- A corrupted fallback corpus must fail closed, not hide behind a search outage.
- A streamed repair must use the same per-request citation boundary as the initial answer.
- A slow/disconnected HTTP response must release the caller budget without unbounded body allocation.
- Index publication must not accept an unvalidated candidate or mutate the live pair automatically.
- Concurrent selected/fallback requests must never share the wrong explanation cache key or validator.

### Task 1: immutable candidate indexes and API

Files: retrieval_service/index.py (offline build/frozen load), engine.py (search and graph port), api.py (ASGI/auth/limits/deadline/admission), lifecycle.py (validate/publish/rollback), tests/test_service.py; no corpus fixture edits.
Interfaces: build_index(agent,wiki,destination,backend,model_path)->index version; load_index(directory,expected_version)->verified frozen corpus/index; Engine.retrieve(request)->bounded metadata response; create_app(engine,auth_mode,local_token)->ASGI app.
Steps: write integrity/publication and HTTP contract tests; run to see missing-module failures; implement manifest inventories, safe deterministic arrays and pinned bytes; implement bounded query/mode/version validation and auth before body parsing; run async tests including timeout/concurrency/source drift and original fixtures; commit this component.
Expected: malformed, unknown, overlarge, unsupported and stale requests never return invented evidence; accepted response contains only verified ID/hash/source metadata; no request can write an index/graph or pick a namespace.

### Task 2: Kotlin request-scoped selection

Files: context/RetrievalContext.kt and RetrievalHttpClient.kt; ExplanationService.kt; CourseQuestionService.kt; CourseExplainer.kt/ExplanationCache.kt; AgentLoop.kt; HermesConfig.kt; retrieval tests.
Interfaces: ContextSelection.select(query)->RequestContext(systemText,evidenceText,validator,identity,abstain); FULL selection is constructor default. Client retrieves JSON only from a validated configured origin with injectable token port and bounded BodySubscriber. Selection resolves IDs against original packaged sidecar/local content.
Steps: write FULL/no-call, selected/separated-policy, bad-response/full-fallback and corrupt-baseline tests; run them RED; implement client/pin validation and request context; wire all three request paths, request-scoped stream validator including repairs and context-identity cache keys; run focused and existing JVM suites; commit.
Expected: unknown/deleted/mismatched sources cannot cross citation gate; all 8 policies persist; FULL default makes zero remote requests and exact old bytes are preserved; outage/version mismatch yields verified original FULL, but corrupted FULL construction fails.

### Task 3: deployment and end-to-end verification

Files: deployment/retrieval/Dockerfile, environment examples, Cloud Run service template, prepare/check/rollback command tooling and README; health/provenance wiring; local E2E harness; EN/KO status notes.
Steps: package API/runtime dependencies separately from evaluation dependencies; add non-root image, immutable index staging, explicit model packaging, no runtime download, sanitized probes and manual-only deployment configuration; run real local Uvicorn HTTP API through Kotlin provider stub and actual citation gate; run lexical and pinned CPU semantic retrieval and supported/unsupported/failure fixtures; use prior actual Neo4j integration results and label any additional graph test accurately; validate artifact syntax and relevant regressions; commit locally.
Expected: no workflow/deploy/push side effects, no secret values, default FULL remains; authentication/reader privilege deployment preconditions are explicit and locally mocked auth is not claimed as cloud IAM verification.

## Native execution ledger

Document task results and any ruled changes in docs/retrieval-deployment/verification.json and implementation-ledger.md. Request one fresh whole-branch review after implementation because executing-plans explicitly requires it. Apply critical/important findings and targeted regression tests; do not publish follow-up branch.
