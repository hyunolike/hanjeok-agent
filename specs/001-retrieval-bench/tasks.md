---

description: "Task list for Retrieval Bench"
---

# Tasks: Retrieval Bench

**Input**: Design documents from `/specs/001-retrieval-bench/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included, but not as blanket TDD. Test tasks appear where an invariant
would otherwise be unverifiable at the moment it breaks — citation validation
(SC-002 is zero-tolerance), the loader seam (Principle III fails silently), the
metric applicability rule (FR-011 produces a plausible wrong number), and pair
validity. Ordinary wiring is not test-first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable — different files, no dependency on an incomplete task
- **[Story]**: US1–US4 from spec.md

## Path Conventions

Single Python package at `bench/`, sibling to `server/` and `frontend/`. Paths
below are repository-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A runnable, lintable, testable skeleton that CI ignores.

- [X] T001 Create the package skeleton from plan.md's tree in `bench/src/bench/` with empty `corpus/`, `graph/`, `answer/`, `eval/` packages and `bench/tests/{unit,contract,integration}/`
- [X] T002 Write `bench/pyproject.toml` pinning Python 3.13 and declaring fastapi, langgraph, langchain-core, langchain-openai, langchain-neo4j, neo4j, ragas, pyyaml, pytest; lock with `uv sync`
- [X] T003 [P] Configure ruff and formatting in `bench/pyproject.toml`
- [X] T004 [P] Configure pytest in `bench/pyproject.toml` with markers `integration` and `costly`, defaulting to deselect both so a bare `uv run pytest` needs no Docker, no network and no key
- [X] T005 [P] Write `bench/docker-compose.yml` with Neo4j 5.x, a named volume and the ports quickstart.md assumes
- [X] T006 [P] Add `bench/runs/` and `bench/reports/` with `.gitkeep`, and add `bench/.venv/` plus `bench/**/__pycache__/` to the repository `.gitignore`

**Checkpoint**: `uv run pytest` passes with zero tests collected and no services running.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The seam, the graph, and the fakes every story depends on. No user
story can start until this phase is done.

- [X] T007 Define `LoadedDoc` exactly as data-model.md specifies in `bench/src/bench/corpus/loader.py`, with `attrs` as an opaque mapping and a `CorpusLoader` protocol
- [X] T008 [P] Implement heading-path chunking in `bench/src/bench/corpus/chunk.py` — split at markdown headings, keep the heading path, never merge across documents, leave short documents whole
- [X] T009 [P] Write `bench/tests/unit/test_chunk.py` covering a document with no headings, nested headings, and a document shorter than the target size
- [X] T010 Implement the travel-context-wiki loader in `bench/src/bench/corpus/wiki.py`: parse frontmatter into `LoadedDoc`, resolve `[[wikilinks]]` and `sources:` within the corpus, and return unresolved references as a reported list rather than failing the load
- [X] T011 Write `bench/tests/unit/test_wiki_loader.py` asserting an unresolved link is reported and dropped while the load still succeeds (spec edge case), and that `conflicts` arrives as verbatim prose in `attrs`
- [X] T012 Implement `bench/src/bench/graph/store.py`: driver lifecycle, constraint on `(corpus, path)`, `Doc.path` lookup index, and the `Chunk.embedding` vector index
- [X] T013 Implement `bench/src/bench/graph/build.py` writing `Doc`, `Tag`, `Source`, `Chunk` and the four edge types from a `LoadedDoc` stream, copying `attrs` onto `Doc` without reading any key
- [X] T014 Capture the corpus git revision at load time and store it with the corpus record in `bench/src/bench/graph/store.py` (FR-012, and the pair validity rule depends on it)
- [X] T015 [P] Implement a deterministic fake embedder and a scripted fake chat model in `bench/tests/conftest.py` so unit tests never load the real model or call an API
- [X] T016 [P] Build a tiny synthetic corpus — a third one, unlike both real ones — as a `CorpusLoader` inside `bench/tests/unit/test_loader_seam.py`, with tests that fail the moment anything downstream branches on a corpus name (Principle III). *Implemented in code rather than as markdown under `tests/fixtures/`: the seam is `LoadedDoc`, so constructing those directly tests it at the right level, and files on disk would only exercise the wiki loader a second time.*

**Checkpoint**: `uv run bench corpus load wiki` writes a graph; `uv run pytest` is green offline.

---

## Phase 3: User Story 1 — Answer one corpus and show where it came from (P1) 🎯 MVP

**Goal**: A question in, a grounded answer out, naming documents a reader can open.

**Independent test**: Load the wiki, ask ten questions whose answers are in it,
confirm every cited path exists and every claim is in the passage that was cited.

- [X] T017 [P] [US1] Implement vector search over `Chunk` in `bench/src/bench/graph/query.py`, filtered by corpus
- [X] T018 [US1] Add one-hop expansion in `bench/src/bench/graph/query.py` — from seed chunks' documents, follow `LINKS_TO`, shared `CITES` and shared `TAGGED`, returning expansion as title plus a one-line summary rather than full text (research §graph expansion, to bound context)
- [X] T019 [US1] Write the single prompt path in `bench/src/bench/answer/prompt.py`: instructions, supplied passages, the citation rule, and the `attrs` block carrying conflicts and status verbatim. **Both arms will use this file and no other** (Principle II)
- [X] T020 [US1] Implement citation validation in `bench/src/bench/answer/citations.py`: every cited path checked against the loaded corpus, whole answer discarded on any miss
- [X] T021 [US1] Write `bench/tests/unit/test_citation_gate.py` including the `fabricated` case quickstart.md names — asserting the rejection carries no answer text (SC-002)
- [X] T022 [US1] Implement the LangGraph pipeline in `bench/src/bench/answer/pipeline.py`: nodes retrieve → answer → validate, `add_conditional_edges` routing validation failure to repair and back exactly once, budget in state, `InMemorySaver` checkpointer
- [X] T023 [US1] Implement the `graph` strategy in `bench/src/bench/answer/strategies.py` as passage selection only, returning passages to the shared pipeline
- [X] T024 [US1] Implement `POST /bench/ask` and `GET /bench/corpora` in `bench/src/bench/api.py` per contracts/http-api.md, with `question` length-bounded and no default for `corpus` or `strategy`
- [X] T025 [US1] Write `bench/tests/contract/test_ask_contract.py` covering answered, `no_grounds` with `answer: null`, 422 without answer text, 409 for an unloaded corpus
- [X] T026 [US1] Implement `POST /bench/corpora/{name}/rebuild` in `bench/src/bench/api.py`, returning counts and the dropped-reference list (FR-014)
- [X] T027 [US1] Add `bench ask` and `bench corpus load|rebuild` to `bench/src/bench/cli.py` with `--show-supplied`

**Checkpoint**: Phase 3 implementation is complete. Verification: 61 offline tests and 19 actual Neo4j integration tests passed. A paid smoke answered 9 of 10 known questions and declined an unsupported question; one known question missed its evidence during retrieval. This is a demonstrable MVP with a recorded retrieval limitation, not a comparative quality result. See [execution evidence](../../bench/reports/phase3-smoke.md).

---

## Phase 4: User Story 2 — Ask the same question both ways (P1)

**Goal**: Two answers to one question whose inputs differ only in supplied passages.

**Independent test**: Run one question through both arms and diff their recorded
inputs; only `supplied` may differ.

- [X] T028 [US2] Implement the `whole` strategy in `bench/src/bench/answer/strategies.py` — supply every chunk of the corpus, and fail with an explicit cause when the corpus exceeds what one prompt can carry rather than truncating (spec US4 scenario 2)
- [X] T029 [US2] Define the run record of data-model.md in `bench/src/bench/eval/runner.py` and append it as JSONL under `bench/runs/`, recording failures with their outcome rather than omitting them
- [X] T030 [US2] Implement pairing in `bench/src/bench/eval/runner.py`, including the validity rule: differing `corpus_revision` marks the pair invalid instead of comparing it
- [X] T031 [US2] Write `bench/tests/unit/test_pair_validity.py` asserting a mismatched-revision pair is excluded and reported, not scored
- [X] T032 [US2] Write `bench/tests/unit/test_arms_share_inputs.py` asserting both strategies produce identical prompt inputs except supplied passages — the automated form of quickstart check 4 (Principle II)
- [X] T033 [US2] Add `bench pair --question-id --corpus --show-diff` to `bench/src/bench/cli.py`

**Checkpoint**: Quickstart check 4 passes. Both strategies run independently and `bench pair` persists both arms plus validity. Final verification after review fixes: 88 offline tests / 26 real Neo4j integration tests passed; three actual wiki pairs have identical common inputs. See [Phase 4 evidence](../../bench/reports/phase4-smoke.md).

---

## Phase 5: User Story 3 — Score a question set (P2)

**Goal**: Numbers per strategy, with `n` and applicability beside them.

**Independent test**: Run the set twice against an unchanged corpus; every score
moves by less than 0.05 (SC-004).

- [X] T034 [P] [US3] Implement question-set loading and schema validation in `bench/src/bench/eval/questions.py` for the YAML of data-model.md, rejecting a `single_doc` entry with empty `reference_docs`
- [X] T035 [US3] Write roughly 30 questions to `bench/questions/wiki-v1.yaml`, mixing `single_doc`, `multi_doc` and `unanswerable`, with `reference_docs` drawn from the real wiki
- [X] T036 [US3] Implement unattended execution of a set across both arms in `bench/src/bench/eval/runner.py`, continuing past a failed run
- [X] T037 [US3] Wire RAGAS in `bench/src/bench/eval/score.py`: faithfulness and answer relevancy for both arms, context precision and recall for `graph` only
- [X] T038 [US3] Implement the applicability rule in `bench/src/bench/eval/score.py` — `not_applicable` with a reason for the `whole` arm's retrieval metrics, never a zero (FR-011)
- [X] T039 [US3] Write `bench/tests/unit/test_evaluation.py` asserting the `whole` arm never receives a numeric context-precision score
- [X] T040 [US3] Build the report of data-model.md in `bench/src/bench/eval/score.py`, stamped with corpus revision, question-set revision, judge model and timestamp, carrying `n` per score and a `by_kind` split
- [X] T041 [US3] Implement `POST /bench/run` returning 202 and `GET /bench/reports/{id}` in `bench/src/bench/api.py` per contracts/http-api.md
- [X] T042 [US3] Add `bench run` and `bench report` to `bench/src/bench/cli.py`
- [ ] T043 [US3] Run the set twice unchanged and record whether SC-004's 0.05 tolerance holds; if it does not, amend the tolerance in `specs/001-retrieval-bench/spec.md` with the observed variance rather than quietly accepting the drift

**Checkpoint**: quickstart check 6 passes; one report exists for the wiki.

---

## Phase 6: User Story 4 — Grow the corpus until the answer flips (P3)

**Goal**: The curve, and the crossing point read off it.

**Independent test**: Run one set at two sizes; `whole` prompt tokens grow with
size while `graph` stays flat.

- [ ] T044 [P] [US4] Implement the work-log vault loader in `bench/src/bench/corpus/worklog.py` — `project`/`type`/`tech`/`status` frontmatter, sparse `[[links]]`, no `sources`
- [ ] T045 [US4] Write `bench/tests/unit/test_worklog_loader.py` asserting `status: 폐기` survives into `attrs` and reaches the answer step
- [ ] T046 [US4] Implement deterministic size sampling at 25/50/100/200/340 in `bench/src/bench/corpus/worklog.py`, seeded and recorded so a size is reproducible (research §1)
- [ ] T047 [US4] Write `bench/questions/worklog-v1.yaml`, with every `reference_docs` entry present in the smallest sample so a question does not become unanswerable purely by sampling
- [ ] T048 [US4] Extend the runner in `bench/src/bench/eval/runner.py` to accept `sizes` and record `corpus_size` per run
- [ ] T049 [US4] Add `--by-size` to `bench report` in `bench/src/bench/cli.py`, reporting supplied-token count per strategy per size (SC-005)
- [ ] T050 [US4] Run the curve and write the finding — including the crossing point, or the honest statement that the curve did not cross within the sizes available — to `bench/reports/README.md`

**Checkpoint**: quickstart check 8 passes; the subproject has answered its question.

---

## Phase 7: Polish & Cross-Cutting

- [X] T051 [P] Write `bench/README.md` pointing at quickstart.md and stating plainly that this measures and does not migrate anything
- [ ] T052 [P] Add structured per-run logging in `bench/src/bench/eval/runner.py` — retrieval size, expansion count, repair count, outcome — since the Kotlin service's gap was exactly this
- [ ] T053 Walk `specs/001-retrieval-bench/quickstart.md` end to end on a clean checkout and fix every step that does not work as written
- [ ] T054 Confirm `./gradlew build` and `pnpm build` are still unaware of `bench/`, and that CI is unchanged

---

## Dependencies

```
Setup (T001–T006)
  └─> Foundational (T007–T016)   ← blocks everything
        ├─> US1 (T017–T027)      ← MVP, independently demonstrable
        │     └─> US2 (T028–T033)   needs the pipeline and prompt path
        │           └─> US3 (T034–T043)  needs both arms recorded
        │                 └─> US4 (T044–T050)  needs scoring to exist
        └─> Polish (T051–T054)
```

US2 depends on US1 because Principle II is enforced by both arms sharing
`prompt.py`, which US1 creates. US3 depends on US2 because scoring a comparison
requires a comparison. US4 depends on US3 because a curve of unscored runs is a
chart of nothing.

## Parallel Opportunities

- Setup: T003, T004, T005, T006 together
- Foundational: T008+T009 with T015 and T016; T010/T011 after T007
- US1: T017 alongside T019 and T020 (different files); T018 needs T017
- US3: T034 alongside T035
- US4: T044 alongside T047
- Polish: T051 with T052

## Implementation Strategy

**MVP is Phase 3.** US1 alone answers questions from a corpus with verifiable
citations — worth showing to someone, and it proves the citation rule before any
measurement leans on it.

Stop points that leave something coherent: after US1 (a grounded answerer),
after US2 (two arms, no scores), after US3 (the wiki answered with numbers),
after US4 (the finding).

Fit to a one-to-two week budget: Setup and Foundational are roughly two evenings,
US1 two or three, US2 one, US3 two or three including question writing, US4 two.
US3's question set is the most likely overrun — thirty questions with real
reference documents is slower than it sounds, and T035 is the task to start early
if the schedule tightens.
