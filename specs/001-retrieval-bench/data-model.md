# Phase 1 Data Model: Retrieval Bench

Two shapes live here and should not be confused. The **graph** is derived state,
rebuilt from files at any time, and holds what retrieval walks. The **run
record** is an append-only artifact of measurement, and is never rebuilt —
losing it means losing the evidence.

## Graph (Neo4j, disposable)

### Nodes

**`Doc`** — one unit a citation may name.

| Property | Type | Notes |
|---|---|---|
| `path` | string | Unique within a corpus. Repo-relative, as a citation writes it |
| `corpus` | string | `wiki` or `worklog`. Every query filters on it |
| `title` | string | |
| `doc_type` | string | Wiki: `entity`/`concept`/`comparison`/`query`/`decision`. Work-log: `설계`/`구현`/`트러블슈팅`/`가이드`/`학습`/`현황` |
| `updated` | date | |
| `confidence` | string, nullable | Wiki only |
| `contested` | bool, nullable | Wiki only |
| `conflicts` | list of string, nullable | Prose, carried verbatim. **Not parsed into edges** — the text names documents in sentences, not references, so a parser would break on rewording |
| `status` | string, nullable | Work-log only: `완료`/`구현예정`/`폐기`. A retrieved `폐기` document must reach the answer step with that mark intact |

Constraint: `(corpus, path)` unique.

**`Tag`** — `name`, `corpus`. Wiki tags are a registered set of 20; work-log
`tech` values are open and number roughly 292.

**`Source`** — `path`, `corpus`. Raw evidence a wiki document cites. **Never
citable in an answer**; it exists so two documents that drew on the same
material are one hop apart.

**`Chunk`** — `id`, `text`, `heading_path`, `ord`, `embedding`.

### Edges

| Edge | From → To | Derived from |
|---|---|---|
| `HAS_CHUNK` | Doc → Chunk | Heading split |
| `TAGGED` | Doc → Tag | `tags:` / `tech:` frontmatter |
| `LINKS_TO` | Doc → Doc | `[[wikilink]]` and markdown links resolving inside the corpus |
| `CITES` | Doc → Source | `sources:` frontmatter |

A `LINKS_TO` or `CITES` target that does not resolve is **reported at load time
and dropped**, never invented as a placeholder node. Spec edge case: the load
still succeeds.

### Index

A vector index over `Chunk.embedding`, plus a lookup index on `Doc.path`, which
citation validation hits once per cited path.

### Why `conflicts` is a property and not an edge

Real values look like this:

> `"design-v3 places each attraction in the time slot where its congestion is
> lowest. api-contract-v4 removed the slot axis entirely and derives visit times
> from travel time. v4 supersedes v3 on this point."`

It names files inside prose. Extracting an edge means matching filenames in free
text — which silently produces nothing the day someone rewrites the sentence,
and produces a wrong edge the day two documents share a stem. Carried as text
and supplied with the document, the conflict reaches the answer step in the only
form that is actually reliable.

## Corpus Loader Output (the seam)

Every loader emits this and nothing corpus-specific. Everything downstream sees
only this shape — Principle III.

```
LoadedDoc:
  path, corpus, title, doc_type, updated
  tags: [str]
  links: [str]        # paths inside the same corpus
  sources: [str]      # raw evidence paths; empty for corpora without them
  attrs: {str: any}   # confidence, contested, conflicts, status …
  body: str
```

`attrs` is deliberately loose: it carries fields only one corpus has, without
teaching the pipeline their names. The pipeline copies `attrs` onto the `Doc`
node and supplies it alongside the document at answer time; it never branches on
a key inside it.

## Run Record (artifact, append-only)

One row per (question, strategy, corpus revision). Written as JSONL under
`bench/runs/`.

| Field | Notes |
|---|---|
| `run_id`, `started_at` | |
| `question_id`, `question` | |
| `corpus`, `corpus_revision`, `corpus_size` | `corpus_revision` is the git revision of the corpus. FR-012, SC-007 |
| `strategy` | `whole` or `graph` |
| `supplied` | Passages given to the model: chunk ids, doc paths, character count |
| `answer`, `cited_paths` | |
| `outcome` | `answered`, `no_grounds`, `invalid_citations`, `budget_exhausted`, `load_failed`, `model_failed` |
| `prompt_tokens`, `completion_tokens`, `elapsed_ms` | |
| `model` | Identity and settings, so a pair is comparable |
| `repair_count` | Times validation sent it back |

A failed run is recorded with its outcome, never omitted — spec User Story 2,
scenario 3. Omitting failures silently converts a failure rate into a smaller
denominator.

## Pair

Two runs, same `question_id` and same `corpus_revision`, one per strategy.

**Validity rule**: if the two runs carry different `corpus_revision`, the pair is
marked invalid and excluded from scoring rather than compared. Stated as a spec
edge case; enforced here because by scoring time the two runs look identical
apart from one field nobody would think to check.

## Question Set

Stored as YAML under `bench/questions/`, versioned with the repository.

| Field | Notes |
|---|---|
| `id`, `question` | |
| `kind` | `single_doc`, `multi_doc`, `unanswerable` |
| `reference_docs` | Paths that ought to support the answer. Empty for `unanswerable` |
| `must_contain` | Claims a correct answer has to make. Empty for `unanswerable` |
| `corpus` | Which corpus it is asked against |

`kind` exists because SC-001 and SC-003 are separate criteria measured over
different subsets, and an aggregate over all three would hide exactly the
difference the graph arm is supposed to show.

`unanswerable` entries score as correct when the system declines. Without them a
system that answers everything confidently would score well.

## Report

Produced from runs, one per scoring execution.

| Field | Notes |
|---|---|
| `report_id`, `generated_at` | |
| `corpus`, `corpus_revision`, `corpus_size` | |
| `question_set_revision`, `judge_model` | FR-012 |
| `scores` | Per strategy, per metric: value, `n` computed over, and `not_applicable` with a reason |
| `by_kind` | The same scores split by question `kind` |

`n` sits beside every score because metrics skip runs they cannot compute, and a
mean over 4 of 30 questions is not the same claim as a mean over 30.
