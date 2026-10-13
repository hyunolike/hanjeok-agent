# Implementation Plan: Hanjeok Guide Agent

**Branch**: `002-hanjeok-guide-agent` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-hanjeok-guide-agent/spec.md`

## Summary

A visitor asks a travel question in Korean. A new `guide` package, in the same
Python project as the retrieval bench, resolves the place and date with rules,
lets the model choose from a fixed set of lookups over a graph built from a
Hanjeok export and over two live Hanjeok endpoints, verifies every citation
against what was fetched, and streams the steps and then the answer. Four new
screens in the existing Next.js frontend show the question, the path, the
evaluation and the design values, built first against recorded fixtures. The
whole is evaluated with the bench's RAGAS judge plus judge-free measures, and
deployed with Neo4j in one container on a Hugging Face Space.

Decisions and what was read to reach them are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (`bench/`, as today); TypeScript 5.9 on
Next.js 16 and React 19 (`frontend/`, as today)

**Primary Dependencies**: FastAPI, LangGraph, langchain-openai (transport to
the NVIDIA-hosted model), neo4j driver, sentence-transformers, RAGAS 0.4.3,
all already in `bench/uv.lock`. Frontend adds only the `pretendard` and
`wanted-sans` font packages. No UI, animation or graph library.

**Storage**: Neo4j 5.26, disposable, rebuilt from the export and the wiki.
Embedding cache, run logs and reports as files under `bench/`. Visits in
memory.

**Testing**: pytest (unit and contract offline; integration against local
Neo4j with fake models; `costly` marker for hosted evaluation, never in CI).
Vitest with Testing Library for the frontend, network faked through an
injected `fetchImpl`.

**Target Platform**: One Linux container on a Hugging Face Space for the
service and Neo4j; Vercel for the frontend.

**Project Type**: Web application: an API service and a frontend.

**Performance Goals**: First step visible within 3 s and answer complete
within 60 s for 90% of the stored question set (SC-001). A refresh of about
ten thousand places completes without holding all embeddings in one call.

**Constraints**: Hosted inference is NVIDIA only and paced at one request
start per 3 s process-wide. At most three lookup rounds, one answer call and
one repair per question. No credentials to the Hanjeok database. Two Hanjeok
endpoints only, neither with side effects. Unit tests need no network or key.

**Scale/Scope**: About 10,700 covered places plus their related targets; 18
wiki pages; a question set of at least 60; four new screens and three
restyled; six character poses.

## Constitution Check

*GATE: passed before research; re-checked after design, below.*

| Principle | How this plan satisfies it | Risk |
| --- | --- | --- |
| I. Nothing claimed that was not measured | SC-006 sets no winner. The eval page shows every number with its sample count, export hash, question-set revision and recording time. README sentences about the guide cite a report id | The demo itself invites "it works" claims. The home page links to the report and says what was and was not measured |
| II. Strategies share everything but retrieval | `vector` and `graph` differ by one lookup being offered. One prompt, one model setting, one budget, one gate, one judge, one live recording. A test asserts the two request payloads differ only in the lookup list | Adding a lookup later that only one arm benefits from. The commit rule in Governance applies |
| III. Loaders replaceable, pipeline not | Hanjeok enters through a loader beside `WikiLoader`. The loader seam gains typed, ranked links, added for both loaders; the wiki loader emits them untyped and unranked as before | The place graph has labels the wiki does not. They are built from loader output only, and `test_loader_seam.py` is extended to cover the new fields |
| IV. A citation is checked before it is shown | One gate over the set of ids the question's steps produced. The answer is sent only after it passes; it is not token-streamed | Two citation kinds double the ways to be wrong. The gate treats them as one set of strings |
| V. Failures are loud | Every non-answer ends with a cause from a fixed list and a message. A failed refresh leaves the previous generation active and reports. No fallback between strategies | The fixture replay in the frontend could hide a dead backend. Replay is on only when the base URL is unset, and the page says it is a recording |
| VI. The model decides nothing about ranking | Alternatives come from Hanjeok's endpoint in its order. Relatedness is read ordered by Hanjeok's rank. The model's action is an enum; arguments are validated; places are reachable only if already fetched | The model reordering in prose. `ALTERED_ORDER` counts it on every evaluated answer |

Constraints: Python for this subproject, yes. Graph disposable, yes, with
generations. Evaluation never in CI, yes. Corpus read-only, yes. Export file
only and no credentials, yes. Date-bound facts live, yes: congestion and
alternatives are never stored in the graph.

**Post-design re-check**: no violations. One clarification is added in the
first task: the 001 documents describe the bench as a local experiment, and the
constitution now says that the `guide` package is deployed while the bench's
comparison stays local.

## Project Structure

### Documentation (this feature)

```text
specs/002-hanjeok-guide-agent/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── guide-api.md
│   ├── hanjeok-export.md
│   └── screens.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
bench/
├── src/
│   ├── bench/                       # unchanged except the loader seam
│   │   └── corpus/loader.py         # + typed, ranked links
│   └── guide/
│       ├── export.py                # read and verify a Hanjeok export
│       ├── loader.py                # HanjeokLoader
│       ├── graph/
│       │   ├── schema.py            # Place, Region, Event, indexes
│       │   ├── refresh.py           # generations, embedding cache
│       │   └── read.py              # search, detail, related, events
│       ├── live.py                  # two Hanjeok endpoints, record/replay
│       ├── scope.py                 # rules before the first model call
│       ├── lookups.py               # the fixed set, validation, declared pages
│       ├── agent.py                 # LangGraph: scope → resolve → act → answer → verify → repair
│       ├── citations.py             # id scheme and gate
│       ├── forbidden.py             # six counters
│       ├── visits.py                # in-memory visits and usage limits
│       ├── api.py                   # /guide/*, SSE
│       ├── cli.py                   # guide refresh | eval | publish
│       └── eval/
│           ├── questions.py         # question set v2
│           ├── run.py               # both strategies from one recording
│           └── report.py
├── questions/hanjeok-v1.yaml
├── tests/
│   ├── fixtures/hanjeok-export/     # synthetic
│   ├── unit/guide/
│   ├── contract/guide/
│   └── integration/guide/
├── Dockerfile                       # service + Neo4j, for the Space
└── docker-compose.yml               # unchanged

frontend/
├── public/brand/guide/              # six poses, WebP
└── src/
    ├── app/
    │   ├── globals.css              # design values
    │   └── [lang]/
    │       ├── ask/
    │       ├── graph/
    │       ├── eval/
    │       └── design/
    ├── components/ui/               # Button, Badge, Chip, Card, Sheet, Field, Notice, StepList
    ├── components/guide/            # Character, CitationChip, PathView
    └── lib/
        ├── guide.ts                 # client, SSE reader, replay
        ├── guide-schema.ts          # zod
        └── guide-fixtures.ts        # recorded streams

design/guide-character/v1/           # sources, prompts, provenance
docs/prd/hanjeok-guide-agent.md      # the course's PRD, written from the spec
```

**Structure Decision**: A second package in the existing Python project and
new routes in the existing frontend. `server/`, `harness/`,
`retrieval-service/` and `experiments/` are not changed. Reasons are in
research decisions 1 and 17.

## Order of work

Screens first, as the author asked, which the fixture replay makes possible:

1. Design values, shared components and the character placeholder.
2. Guide client, schemas and recorded fixtures; the ask screen in every state.
3. Path view, evaluation page and design page, from fixtures.
4. Export reader, loader, graph schema and refresh, on the synthetic export.
5. Lookups, scope rules, agent, gate, API. The frontend switches from replay
   to the real service with no change to its screens.
6. Question set, evaluation run, counters, report.
7. Character assets through Codex; restyle of the existing screens.
8. Deployment spike, then deployment; PRD and README.

The Hanjeok-side export script and the first real export sit outside this
repository. Step 6's published numbers need them; nothing before does.

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| Generations on every graph element | FR-020: a failed refresh must leave the previous copy in use | Drop-and-rebuild, as the bench does, loses the copy on failure |
| Live record/replay | Principle II on data that changes daily | Calling live in both arms lets the arms see different facts and makes a report unrepeatable |
| A shared component directory in the frontend | Six screens share the same controls | Colocating, as the two existing screens do, would copy each control several times |
