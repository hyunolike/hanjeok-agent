# Tasks: Hanjeok Guide Agent

**Input**: Design documents from `/specs/002-hanjeok-guide-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Written before the code they cover, as this repository already does.
Hosted-model evaluation is never part of the test run.

**Organisation**: Screens come first, per the author's direction, and run on
recorded fixtures until the service exists. Each phase ends at a checkpoint
that leaves something coherent. `[P]` marks tasks in different files with no
dependency between them.

## Phase 1: Setup

- [X] T001 Amend `.specify/memory/constitution.md` Constraints: the `guide` package is deployed; `bench` measurement stays local
- [X] T002 [P] Run `pnpm install` in `frontend/` and read the Next.js 16 guides under `frontend/node_modules/next/dist/docs/` that cover routing, fonts and static assets, as `frontend/AGENTS.md` requires
- [X] T003 [P] Add `pretendard` and `wanted-sans` to `frontend/package.json`; add `NEXT_PUBLIC_GUIDE_BASE_URL` to `frontend/.env.example`
- [ ] T004 [P] Add the `guide` package to `bench/pyproject.toml` (wheel packages, `guide` script entry) and create `bench/src/guide/__init__.py`
- [ ] T005 [P] Add bench steps to `.github/workflows/build.yml`: `uv sync`, `ruff check`, `pytest` (offline markers only)

## Phase 2: Design foundation (FR-033, FR-038)

- [X] T006 Write the design values in `frontend/src/app/globals.css` as Tailwind 4 `@theme`: raw scales, then the purpose-named values of `contracts/screens.md`, light and dark
- [X] T007 Load Pretendard and Wanted Sans in `frontend/src/app/[lang]/layout.tsx`
- [X] T008 [P] `Button`, `Field`, `Chip` with tests in `frontend/src/components/ui/`
- [X] T009 [P] `Badge`, `Card`, `Notice` with tests in `frontend/src/components/ui/`
- [X] T010 [P] `Sheet` in `frontend/src/components/ui/`, carrying over the Esc, backdrop and focus behaviour of `CitationSheet.tsx`, with tests
- [X] T011 [P] `Character` in `frontend/src/components/guide/Character.tsx`: six states, decorative image with required adjacent text, still under reduced motion; reads `frontend/public/brand/guide/<state>.webp`, which T053–T054 produce; tests
- [X] T012 Add `guide`, `graph`, `evalPage` and `design` namespaces to `frontend/src/lib/i18n.ts` in `ko` and `en`
- [X] T013 `/[lang]/design` page: swatches, type, components in each state, six poses, contrast ratio beside each colour pair; test that every purpose-named value renders

**Checkpoint**: `/ko/design` shows the system in both appearances. `pnpm typecheck && pnpm test && pnpm build` pass.

## Phase 3: User Story 1 on fixtures — ask and see the steps (P1)

- [X] T014 [P] [US1] zod schemas for every event and response of `contracts/guide-api.md` in `frontend/src/lib/guide-schema.ts`, with tests
- [X] T015 [P] [US1] Recorded streams in `frontend/src/lib/guide-fixtures.ts`: answered, partial, ambiguous, no-data, declined, failed, usage limit, stream cut
- [X] T016 [US1] `askGuide` in `frontend/src/lib/guide.ts`: SSE reader with injectable `fetchImpl`, exactly one terminal outcome, replay when the base URL is unset; tests for each fixture and for a stream cut mid-step
- [X] T017 [P] [US1] `StepList` in `frontend/src/components/ui/StepList.tsx`: running, ok, refused, no-data, failed; collapsible; tests
- [X] T018 [P] [US1] `CitationChip` and record/policy sheet content in `frontend/src/components/guide/`, the two kinds visibly different; tests
- [X] T019 [US1] `/[lang]/ask` page and `AskGuide` client component: every state of `contracts/screens.md`, follow-up questions, candidate choice resuming the question; tests per state
- [X] T020 [US1] Entry point to `/[lang]/ask` on the home page in `frontend/src/app/[lang]/page.tsx`, existing strings untouched

**Checkpoint**: Story 1 is demonstrable end to end in the browser from recordings.

## Phase 4: User Stories 2 and 3 on fixtures — path and evaluation (P2)

- [X] T021 [P] [US2] Deterministic layout for a path (start centred, related by rank, groups for region and documents) in `frontend/src/components/guide/path-layout.ts`, with tests on positions and order
- [X] T022 [US2] `PathView` SVG and its equivalent list in `frontend/src/components/guide/PathView.tsx`, opened inline under the answer on `/[lang]/ask`; tests that every node and edge of the `path` event appears and nothing else
- [ ] T023 [US2] `fetchPlaces`, `fetchPlace`, `fetchStatus` in `frontend/src/lib/guide.ts` with fixtures and tests
- [ ] T024 [US2] `/[lang]/graph` page: from an answer, browsing by name, place panel, not-found; refresh time shown; tests per state
- [ ] T025 [P] [US3] Fixture report and sample in `frontend/src/lib/guide-fixtures.ts`; `fetchEvalReport`, `fetchEvalSample` with tests
- [ ] T026 [US3] `/[lang]/eval` page: provenance line, metric table with sample counts, "not scored" cells, forbidden behaviours, by-kind table, identical-inputs statement, limitations, sample view, no-report state; tests per state

**Checkpoint**: All four new screens work from fixtures at 360px and desktop width.

## Phase 5: Service foundation — export, loader, graph (blocks Phases 6–8)

- [ ] T027 [P] Synthetic export in `bench/tests/fixtures/hanjeok-export/` and a broken copy in `hanjeok-export-broken/`, per `contracts/hanjeok-export.md`
- [ ] T028 [P] Recorded Hanjeok responses for the synthetic places in `bench/tests/fixtures/hanjeok-live/`: covered, uncovered, date out of range, alternatives
- [ ] T029 `bench/src/guide/export.py`: read an export, verify hashes and counts, named causes on mismatch; unit tests
- [ ] T030 Extend the loader seam in `bench/src/bench/corpus/loader.py` with typed, ranked links; `WikiLoader` emits them as before; extend `tests/unit/test_loader_seam.py`; confirm the bench's 130 offline tests still pass
- [ ] T031 `bench/src/guide/loader.py` `HanjeokLoader` over an export; unit tests
- [ ] T032 `bench/src/guide/graph/schema.py`: labels, constraints, `place_embedding` index; integration test
- [ ] T033 `bench/src/guide/graph/refresh.py`: batched embedding with an on-disk cache keyed by content hash, write a generation, verify counts, move the pointer, delete the old; integration tests including a refresh that fails before the pointer moves (FR-020)
- [ ] T034 [P] `bench/src/guide/graph/read.py`: search through the vector index filtered by active generation, name match, detail, related ordered by rank, events; integration tests including rank order and generation isolation
- [ ] T035 [US4] `guide refresh --export <dir>` in `bench/src/guide/cli.py`: prints counts and generation, non-zero exit with cause on failure; tests

**Checkpoint**: Story 4 passes on the synthetic export. Discard and rebuild gives the same graph (SC-007).

## Phase 6: User Story 1 on the service (P1)

- [ ] T036 [P] [US1] `bench/src/guide/live.py`: the two endpoints, envelope handling, `hasCongestionData: false` as its own outcome, timeouts, per-question cache, record and replay modes; unit tests against the recordings
- [ ] T037 [P] [US1] `bench/src/guide/scope.py`: unsupported topics, rule override, off-topic, date parsing relative to today, reference resolution from earlier questions only, name resolution with ambiguity; unit tests for every edge case in the spec
- [ ] T038 [P] [US1] `bench/src/guide/citations.py`: id scheme, gate over the fetched set; unit tests
- [ ] T039 [US1] `bench/src/guide/lookups.py`: the seven lookups, input limits, the "already fetched" rule, refusal reasons, declared wiki pages, produced ids; unit tests per lookup including each refusal
- [ ] T040 [US1] `bench/src/guide/agent.py`: LangGraph with scope, resolve, act (structured next-action, enum of lookups), answer, verify, repair; three-round and 60-second budgets with lookups withdrawn on the last call; unit tests with a scripted model for answered, partial, refused-then-corrected, invalid citations repaired, invalid twice, budget spent, service unreachable
- [ ] T041 [P] [US1] `bench/src/guide/visits.py`: visit ids, turns without answer text, expiry, per-visitor and daily limits; unit tests
- [ ] T042 [US1] `POST /guide/ask` in `bench/src/guide/api.py`: SSE in the order of the contract, one terminal event on every path, 400/429/503 bodies, CORS from configuration; contract tests reading the same recorded stream the frontend fixtures use
- [ ] T043 [US1] Regenerate `frontend/src/lib/guide-fixtures.ts` from the service's contract-test recordings so both sides test one shape; run the frontend against the local service

**Checkpoint**: Story 1 works in the browser against the local service on the synthetic export.

## Phase 7: User Story 2 on the service (P2)

- [ ] T044 [P] [US2] `GET /guide/places`, `GET /guide/places/{id}`, `GET /guide/status` in `bench/src/guide/api.py`; contract tests
- [ ] T045 [US2] Build the `path` event from the steps of a question in `bench/src/guide/agent.py`; test that it contains exactly what was fetched (FR-022)

**Checkpoint**: The path view shows real paths.

## Phase 8: User Story 3 on the service (P2)

- [ ] T046 [P] [US3] `bench/src/guide/eval/questions.py`: question set v2, validation of counts per kind and of every `needs` id; unit tests
- [ ] T047 [P] [US3] `bench/src/guide/forbidden.py`: six counters with a gazetteer matcher; unit tests with real sentences for each, including a "no data" place described as quiet
- [ ] T048 [US3] `bench/src/guide/eval/run.py`: record live responses once, run both strategies from the recording, append run records; a test asserting the two arms' model inputs differ only in the offered lookups (Principle II)
- [ ] T049 [US3] `bench/src/guide/eval/report.py`: RAGAS metrics through the bench judge, id-based precision and recall, counters, by-kind split, not-scored handling, provenance, limitations; unit tests with a fake judge
- [ ] T050 [US3] `guide eval` and `guide publish` in `bench/src/guide/cli.py`; `GET /guide/eval/latest`, `/{id}`, `/{id}/samples/{qid}`; contract tests
- [ ] T051 [US3] `bench/questions/hanjeok-synthetic-v1.yaml`: a small set over the synthetic export, used by tests and the quickstart

**Checkpoint**: An evaluation runs end to end on the synthetic export and its report renders on `/ko/eval`.

## Phase 9: Character assets and restyle (FR-032, FR-034–FR-037)

- [ ] T052 Write the character brief and six pose prompts in `design/guide-character/v1/prompt.txt`, with the approved sun guide as the stated style reference
- [ ] T053 Generate the six poses through Codex image generation; store 512×512 transparent PNG sources in `design/guide-character/v1/`
- [ ] T054 Export 384×384 WebP to `frontend/public/brand/guide/`, replacing the placeholders; record tool, prompts, references, edit steps and SHA-256 in `design/guide-character/v1/provenance.json` with `status: draft` and `rightsReviewStatus: pending`
- [ ] T055 [P] Move `frontend/src/lib/grades.ts` and the existing course, evidence and home components to the design values; existing tests pass unchanged
- [ ] T056 Set the nav brand and metadata title consistently in `frontend/src/lib/i18n.ts` and `layout.tsx`
- [ ] T057 Run SC-010 with five people on `/ko/design` and record the result in `specs/002-hanjeok-guide-agent/checklists/character-recognition.md`

**Checkpoint**: The demo has one visual language and its character, marked draft.

## Phase 10: Real data, deployment and documents

- [ ] T058 Hanjeok-side export script, in the Hanjeok repository, when the author asks for it; produce the first real export
- [ ] T059 `guide refresh` on the real export; record counts and timings; decide from them whether research decision 2 needs a cap
- [ ] T060 Write `bench/questions/hanjeok-v1.yaml`: at least 60 questions, at least 8 of each kind, `needs` ids verified against the real generation (SC-005)
- [ ] T061 Run and publish the evaluation; commit run records and the report
- [ ] T062 Deployment spike: `bench/Dockerfile` running the service and Neo4j in one container on a Space; measure memory and import time; record the result and the fallback decision in `research.md`
- [ ] T063 Deploy the service; set `GUIDE_CORS_ALLOWED_ORIGINS`; point the Vercel frontend at it; walk through `quickstart.md`
- [ ] T064 [P] `docs/prd/hanjeok-guide-agent.md` from the spec, in Korean
- [ ] T065 [P] Update `README.md` and `README.ko.md`: what the guide is, the four screens, the report the claims rest on; keep the heading anchors the home page links to
- [ ] T066 SC-008 walk-through by a reviewer who has not seen the code; record the time taken

## Dependencies

- Phase 2 blocks Phases 3 and 4. Phases 3 and 4 do not need the service.
- Phase 5 blocks Phases 6, 7 and 8. It does not need the frontend.
- Phase 6 before T043, which joins the two sides.
- Phase 9 can run any time after Phase 2.
- T058 blocks T059–T061. T062 blocks T063. T061 and T063 block T065 and T066.

## Parallel opportunities

Phases 3–4 (frontend) and Phase 5 (service) can proceed together. Within a
phase, tasks marked `[P]` touch different files.

## Implementation strategy

Stop at any checkpoint and something works: the design page, the ask screen on
recordings, all screens on recordings, a graph that refreshes safely, a real
answer, a real path, a real report, a deployed demo.

## Needs the author

- T053–T054: whether the character assets appear on the public demo, given
  that Hanjeok's own legal review marks its brand assets as blocked for public
  release (research decision 19).
- T058: a change in the Hanjeok repository.
- T057, T066: people.
- T061, T063: model quota and deployment accounts.
