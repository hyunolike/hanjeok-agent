# Implementation Plan: Retrieval Bench

**Branch**: `001-retrieval-bench` (working branch `feat/graphrag-bench`) | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-retrieval-bench/spec.md`

## Summary

Build the retrieval arm this repository never built, run it against the
whole-corpus prompting it already argues for, and report their measured quality
and cost on the existing wiki. The 2026-10-13 scope correction excludes personal
worklogs and document-size sampling.

A Python subproject under `bench/` loads the wiki into a graph store, answers
questions two ways — every passage supplied, or passages selected by similarity
and widened along document links — and scores both with a model judge. The
existing Kotlin service is not touched; whole-corpus prompting is reimplemented
here so that both arms go through one prompt path, which Principle II requires
and which comparing across two languages would make impossible.

## Technical Context

**Language/Version**: Python 3.13, dependencies managed with `uv`

**Primary Dependencies**: FastAPI (HTTP), LangGraph (answer pipeline as a state
graph), LangChain (chat-model, embedding and Neo4j vector interfaces only —
loaders are written here, see research §6), RAGAS (scoring), Neo4j Python driver

**Storage**: Neo4j 5.x in Docker, holding both the graph and the passage vector
index. Entirely derived: droppable and rebuildable from corpus files at any
time. Run and metric records are JSONL; reports are atomic JSON files under `bench/runs/` and
`bench/reports/`, which are **not** derived and are committed as evidence.

**Testing**: pytest. Unit and contract tests run with no network, no API key and
no Docker, using a deterministic fake embedder and a scripted model. Integration
tests are marked and need Neo4j. Scoring runs call NVIDIA NIM and never run in
CI.

**Target Platform**: Local developer machine. Not deployed; nothing here goes to
Cloud Run or Vercel.

**Project Type**: Single Python service plus a CLI, inside an existing polyglot
repository.

**Performance Goals**: None. This subproject measures quality and cost per
answer, not throughput, and a latency target would compete with the measurement
for attention.

**Constraints**: Unit suite under 10 seconds so it is run often. A full scoring
pass over 30 questions × 2 arms is minutes and is expected to be; the HTTP
contract returns 202 for it rather than holding a socket.

**Scale/Scope**: The curated wiki only; the measured snapshot has 14 documents
and 57 chunks. The versioned question set contains 30 questions. Additional
corpus loaders and document-size sampling are outside the current scope.

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 design below.*

| Principle | How the design satisfies it | Risk |
|---|---|---|
| I. Nothing claimed that was not measured | Every score carries `corpus_revision`, `question_set_revision`, `judge_model` and `n`. Reports are committed artifacts | Low — enforced by the report schema |
| II. Arms share everything but retrieval | One prompt path, one model config, one question text; the arms are two implementations of "choose passages". `bench pair --show-diff` exists to prove it | **Highest.** Any prompt tweak can violate it while looking like an improvement. Mitigated by the diff check (quickstart 4) and the commit-message rule in the constitution |
| III. Loaders replaceable, pipeline not | `LoadedDoc` is the only shape crossing the seam; corpus-specific fields ride in `attrs`, which the pipeline copies but never branches on | Medium — a `if corpus == "wiki"` downstream would break it silently. Caught by a test that runs the pipeline against a third, synthetic corpus |
| IV. Citations checked before shown | Validation is a node in the graph with a conditional edge; the 422 body carries no answer text | Low |
| V. Failures loud | Fixed `outcome` set, recorded on every run including failures; no fallback from `graph` to `whole` | Low |

**Post-Phase-1 re-check**: passes. One thing tightened during design — the pair
validity rule (`data-model.md`) was added because two runs against different
corpus revisions are indistinguishable at scoring time and would silently
produce a comparison of two different corpora, which is a Principle II violation
arriving through the back door.

## Project Structure

### Documentation (this feature)

```text
specs/001-retrieval-bench/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── http-api.md
└── tasks.md            # /speckit-tasks output — not created here
```

### Source Code (repository root)

```text
bench/
├── pyproject.toml
├── docker-compose.yml          # Neo4j only
├── src/bench/
│   ├── corpus/
│   │   ├── loader.py           # LoadedDoc, the seam
│   │   ├── wiki.py             # travel-context-wiki loader
│   │   └── chunk.py            # heading split
│   ├── graph/
│   │   ├── store.py            # driver, schema, indexes
│   │   ├── build.py            # LoadedDoc -> nodes and edges
│   │   └── query.py            # vector search, one-hop expansion
│   ├── answer/
│   │   ├── pipeline.py         # LangGraph state graph
│   │   ├── strategies.py       # whole | graph
│   │   ├── prompt.py           # the single prompt path both arms use
│   │   └── citations.py        # validation
│   ├── eval/
│   │   ├── questions.py        # question set loading
│   │   ├── runner.py           # pairs, run records
│   │   └── score.py            # RAGAS, applicability rules
│   ├── api.py                  # FastAPI
│   └── cli.py
├── questions/                  # versioned question sets
├── runs/                       # JSONL evidence, committed
├── reports/                    # committed
└── tests/
    ├── unit/
    ├── contract/
    └── integration/
```

**Structure Decision**: A single Python package in `bench/`, beside the existing
`server/` (Kotlin), `frontend/` (Next.js) and `harness/`. It is a sibling, not a
nested module: it shares no build, no dependency file and no deployment with
them, and the only thing it shares with `server/` is the corpus and the citation
rule. Making it a sibling keeps `./gradlew build` and `pnpm build` unaware of it,
which matters because CI runs both and must not start needing Python.

The split inside `src/bench/` follows the seam the constitution names: `corpus/`
knows about markdown and frontmatter, `graph/` and `answer/` know only
`LoadedDoc` and passages, `eval/` knows only runs. A file that imports across
two of those boundaries is the signal that Principle III is slipping.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| A graph database for a small wiki | Exercising a graph store is part of the experiment | An in-memory graph would suffice for this corpus; the database's operational overhead is part of the measured profile. Recorded in research §2 |
| Whole-corpus prompting reimplemented here, duplicating what `server/` does | Principle II: both arms must share one prompt path. Comparing against `server/` would vary language, framework and prompt at once | Calling the existing service would be less code and a worse experiment — the measured difference would include everything that differs between Kotlin and Python |
| A framework for a loop this repository already hand-wrote | The comparison between hand-written loop and framework becomes available for free, over the same rules, in one repository | A plain loop is honestly sufficient for the pipeline itself; research §5 says so plainly |
