# SQLite 안내 API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aura 인증 없이 실제 AI 응답을 제공하는 무료 안내 API 배포.

**Architecture:** 공개 export와 검증한 동일 공간 벡터를 읽기 전용 SQLite로 묶는다.
Places/Policy 어댑터를 바꾸고 기존 API/agent를 유지한다. 압축 산출물을 source build에 포함한다.

**Tech Stack:** Python 3.13, stdlib sqlite3/gzip, 기존 pinned sqlite-vec, NVIDIA HTTP, Render Free.

**Spec:** `docs/superpowers/specs/2026-11-24-guide-sqlite-design.md`

## Global Constraints

- NVIDIA 모델/식별자, SSE/인용/순위 검증, 단일 수정과 방문 제한 유지.
- mode=ro, 8MiB 캐시/mmap=0, API에 로컬 모델과 전체 Python float 행렬 없음.
- 기존 Neo4j 경로/과거 기록 유지, 새 평가를 과거 점수로 표시하지 않음.
- 비용 발생, main 병합, Aura 변경 없음. 기존 배포 승인은 재요청하지 않음.

## Review Focus

- 원문이 바뀐 위키를 과거 벡터와 묶지 않음: 빌더에서 chunk id/order/text/key 대조.
- 지역 필터를 검색 후 적용하지 않음: 더 가까운 다른 지역 행을 둔 실제 DB 테스트.
- 직접 연결 행사를 다른 장소 반경으로 잘못 보여주지 않음: 행사 날짜/반경 테스트.
- 다른 코퍼스 벡터/손상 파일은 ready200이 되지 않음: manifest/identity 테스트.
- 런타임 실패 시 기존 DB로 폴백하지 않음: SQLite 선택 후 missing-file API 테스트.

### Task 1: 파일 스키마와 조회 어댑터 (S2/S4/S5)

Files: `bench/src/guide/sqlite_store.py`, `bench/tests/unit/test_guide_sqlite.py`.

Interfaces: `write_snapshot(path, export, wiki, place_vectors, wiki_vectors, provenance)`;
`SQLiteStore(path, manifest_path, model_id)` owns `places`, `policy`, `meta`, `close()`.
Places/Policy methods exactly match `guide.sources`.

- [x] Write real SQLite tests for deterministic ranking, region prefilter, names, related order,
  events, wiki chunk/page mapping, invalid vectors, read-only and metadata validation.
- [x] Run focused tests; observe missing-feature failure before implementation.
- [x] Implement schema, bounded read-only connection and fixed SQL with sqlite-vec cosine.
- [x] Focused tests pass; commit independently testable store.

### Task 2: 검증된 운영 산출물과 런타임 선택 (S1/S3/S6)

Files: `bench/deploy/prepare_sqlite.py`, `bench/src/guide/api.py`, Task1 tests,
`bench/tests/unit/test_guide_runtime.py`, `bench/Dockerfile.api`, `bench/.dockerignore`,
`deployment/guide-free/{render.yaml,env.example,README.md}`, `bench/data/`.

Interfaces: Task1 writer/store; existing `verified_cache`, `read_export`, `WikiLoader`,
mode=ro cache reader; `GUIDE_STORE=sqlite`, `GUIDE_SNAPSHOT_DB`, `GUIDE_SNAPSHOT_MANIFEST`.

- [x] Write failing integrity/atomic-builder and API selection/readiness tests.
- [x] Add operator CLI that validates cache/source provenance and writes gzip + hashes/metadata.
- [x] Select SQLite explicitly in EnvRuntime; preserve default Neo4j and fail closed.
- [x] Verify Docker artifact hashes while decompressing; free Blueprint uses SQLite, NVIDIA key only.
- [x] Build actual current-data artifact; run focused + full offline suite and Ruff; commit.

### Task 3: 実検証と無料公開 (S7/S8)

Files: `bench/deploy/verify-sqlite-memory.py`, `bench/reports/runtime/sqlite-*.json`,
this plan, review record; frontend production URL configuration only after server ready.

- [ ] Build amd64 image and run real forecast/policy/alternatives under 512MiB/no-swap.
- [ ] Record actual image/peak/OOM/outcomes; review final source in fresh context and fix blockers.
- [ ] Push reviewed feature branch; create Render Free service using existing authorized workspace/key.
- [ ] Verify remote ready/status and real SSE, then rebuild/deploy frontend and inspect public flow.
- [ ] Record achieved results and concrete external blockers; never claim unobserved completion.

## Progress

- Baseline: 4b7b09f, clean feature branch. User approved concrete SQLite transition and direct execution.
- Existing authorization and working checkout reused; no new account/DB or duplicated worktree setup.
- Pre-flight: Task1 store consumed by Task2 runtime/builder; Task2 artifact consumed by Task3 image.
  Contracts consistent. Same stored vectors, exact cosine search replaces approximate Neo4j search.
- Ruling: use existing pinned sqlite-vec C scalar search, no new dependency or Python matrix;
  exact-neighbour boundary rankings can differ, so old quality scores cannot certify this backend.
- Ruling: compressed public-data artifact in source build is needed for source-based Render deployment;
  binary size is checked against repository limits before committing and no secret cache is copied.
- Fresh-context design review completed by sqlite_design_review. Accepted all four details:
  clean pinned chunk-id/order/text binding, read-only cache reader, top3*limit policy candidate
  window, content-addressed gzip publication followed by atomic manifest. No architectural blocker.

- Tasks1/2 complete: clean-cache builder produced12106 places/43087 links/209events/18docs/83chunks; 46.68MiB gzip, hashes verified and no exact API key in artifact/source.
- Final scoped reviewer found four concrete issues; regression tests observed RED→GREEN for manifest shape, Neo4j radius/null-score parity and source-specific smoke. Full519passed/43deselected; Ruff clean.
- Initial actual smoke3/4answered, alternatives model_failed, peak316506112bytes/noOOM preserved. Final corrected80507396 image smoke running; no public deployment claim yet.
