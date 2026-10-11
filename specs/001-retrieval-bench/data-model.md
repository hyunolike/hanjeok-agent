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
| `cause` | Fixed, sanitized failure description; no discarded answer/error text |
| `pair_id`, `corpus_generation` | Link arms; distinguish rebuilds at the same revision |
| `inputs` | Captured first-request system/user, output schema and shared budgets; user carries full supplied text/attributes |
| `retrieval` | Selection profile: all chunks or corpus-filtered exact cosine with expansion bounds |
| `model_calls` | Attempted provider calls; zero means selected inputs were not submitted |

Runs lacking a usable corpus snapshot record unknown revision/generation/size
as null, never a guessed revision. Such runs remain evidence of failure but
cannot form a valid pair. An exception with no reported usage records zero
tokens and its attempted-call count; zero does not establish zero billing.

A failed run is recorded with its outcome, never omitted — spec User Story 2,
scenario 3. Omitting failures silently converts a failure rate into a smaller
denominator.

## Pair

Two runs, same `question_id` and same `corpus_revision`, one per strategy.

**Validity rule**: if the two runs carry different `corpus_revision`, the pair is
marked invalid and excluded from scoring rather than compared. Stated as a spec
edge case; enforced here because by scoring time the two runs look identical
apart from one field nobody would think to check.

Phase 4 also verifies generation, corpus size, question ID/text, model settings,
and all captured common input fields. A same-revision rebuild changes generation
and conservatively invalidates a pair. Missing snapshot/input metadata prevents
comparison. A valid pair with a failed arm is retained but ineligible for scoring.
Append-only companion `.pairs.jsonl` rows link the two run IDs and store validity,
cause and the input diff; each `.jsonl` run row remains one strategy execution.

## Question Set

Stored as YAML under `bench/questions/`, versioned with the repository.
The file is `{id: <set-name>, questions: [...]}` and its revision is the
SHA-256 of the exact bytes read. Set IDs and question IDs are safe identifiers;
question IDs must be unique. A set contains 1–100 questions. Unknown fields,
blank text, duplicate/unsafe references and malformed kinds are rejected.

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
`single_doc` requires exactly one canonical reference, `multi_doc` at least
two, and both need nonempty factual claims. Unsupported questions have neither.
Before any inference, every reference is checked against the loaded corpus and
every question must name the requested corpus. `must_contain` is joined into
RAGAS's reference answer; it is not an exact-text matching rule.

## Report

Produced from runs, one per scoring execution.

| Field | Notes |
|---|---|
| `report_id`, `status`, `timestamp` | UUID, completed status and UTC generation time |
| `corpus`, `corpus_revision`, `corpus_generation`, `corpus_size` | Frozen loaded profile |
| `question_set`, `question_set_revision`, `question_count` | Name, content hash and requested denominator |
| `answer_model`, `judge_model`, `scoring_policy` | Provider/endpoint/settings, library/embedding revisions and applicability rules |
| `strategies.<arm>.metrics` | Each metric's value, successful `n`, total, failed/skipped/not-applicable counts and reason |
| `strategies.<arm>.by_kind` | The same aggregates split by question kind |
| `strategies.<arm>.outcomes`, `attempted`, `abstention` | All requested outcomes and unsupported-question denominator/accuracy |
| `strategies.<arm>.answer_usage`, `judge_usage` | Separate observed provider calls and tokens; no price estimate |
| `scores` | Per-run observations with metric, question/run ID, kind, status, value and fixed cause |
| `pairs`, `included_pairs`, `excluded_pairs` | Frozen comparison eligibility, including failed arms |
| `artifacts` | Answer/pair/score JSONL basenames |

`n` sits beside every score because metrics skip runs they cannot compute, and a
mean over 4 of 30 questions is not the same claim as a mean over 30.
Reports are atomic JSON files under `bench/reports/`, so the same representation
is returned by HTTP and offline CLI reads. JSONL observations are append-only.
Completed reports are identical in both interfaces. Offline reads of a saved
running marker return `unknown` with its saved status and cause; only the
originating HTTP process can establish live ownership. A fresh HTTP process
reports an unowned running marker as interrupted. Neither path claims completion.
Whole retrieval metrics always have null value and `not_applicable` status.
Declines have null answer metrics, not zero. Unsupported-question correctness
requires a normal, eligible decline and uses all requested unsupported questions
as the denominator, so execution failures cannot improve that accuracy.

Faithfulness uses actually supplied passages from cited documents, including
opaque attributes. Graph retrieval metrics use all supplied passages in order.
The reference clauses are used for precision/recall, not faithfulness/relevancy.
Judge failures and nonfinite values stay null and count as failures. Answer
relevancy is cosine based and can legitimately be negative.

Repeated reports are compared only when frozen profiles and scored question
membership match and there are no judge failures. The variance artifact records
aggregate and per-kind mean deltas, counts, the maximum delta and the original
0.05 threshold; empty or unequal samples are inconclusive, never a false pass.
