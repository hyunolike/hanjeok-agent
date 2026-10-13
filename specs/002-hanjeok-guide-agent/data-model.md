# Data Model: Hanjeok Guide Agent

Three places hold data: the export files, the graph built from them, and the
records one question produces. The graph is derived and disposable; the export
and the wiki are its only sources.

## Graph

Existing bench labels (`Doc`, `Chunk`, `Tag`, `Source`, `Corpus`) are unchanged
and continue to hold the wiki. The labels below are added.

### Nodes

| Label | Key | Properties | Notes |
| --- | --- | --- | --- |
| `Place` | `(generation, id)` | `name`, `name_key`, `region_code`, `region_label`, `category_mid`, `category_small`, `content_type`, `overview`, `summary`, `address`, `lat`, `lng`, `has_congestion_data`, `embedding` | `id` is Hanjeok's `derived_attraction.id`. `name_key` is the name with spaces removed, for matching. `embedding` is absent when there is no text to embed |
| `Region` | `(generation, code)` | `label` | `code` is the 5-digit district code; `label` is Hanjeok's display string |
| `Event` | `(generation, id)` | `kind`, `name`, `start_date`, `end_date`, `lat`, `lng`, `place_text` | `kind` is `festival` or `exhibition`. `id` is prefixed with its kind |
| `Corpus` | `name` | existing fields, plus `active_generation`, `exported_at`, `export_sha256`, `counts_json` | One `Corpus` named `hanjeok` |

### Relationships

| Type | From → To | Properties | Notes |
| --- | --- | --- | --- |
| `RELATED_TO` | `Place → Place` | `rank`, `score`, `distance_km`, `travel_minutes` | Directed. Always read ordered by `rank`, nulls last, then `score` descending. Never created by the agent |
| `IN_REGION` | `Place → Region` | none | |
| `HELD_AT` | `Event → Place` | none | Exhibitions that Hanjeok tied to a place |

A festival has coordinates and no place or region in the export, so no
relationship is stored for it. The `events` read returns events tied to the
place by `HELD_AT`, plus untied events within 1 km of it. An earlier draft
listed `HELD_IN (Event → Region)`; the export carries no region for events, so
it was dropped rather than derived by guessing.

### Indexes

- Uniqueness on each node key above.
- `place_embedding`: vector index on `Place.embedding`, 1024 dimensions, cosine.
- Range index on `Place.name_key` and on `Place.generation`.

### Generation rule

Every node and relationship above carries `generation`, and every node carries
`corpus`, so a test or a second export never touches another's copy. Reads take the
`active_generation` from `Corpus` first and filter by it. A refresh writes a
new generation, checks its counts against the export manifest, sets
`active_generation`, then deletes other generations. A refresh that fails
before the pointer moves is deleted and reported; the active one is untouched.

## Lookups

The fixed set the model can choose from. Each has validated inputs, a source,
the citation ids it produces and the wiki pages it declares.

| Lookup | Inputs and limits | Source | Produces | Declares |
| --- | --- | --- | --- | --- |
| `search_places` | `text` 1–100 chars; `region_code` optional | graph, vector index | `hanjeok:place/<id>` for up to 5 | none |
| `place_detail` | `place_id` already fetched in this question | graph | `hanjeok:place/<id>` | none |
| `related_places` | `place_id` already fetched; `limit` 1–10 | graph, `RELATED_TO` by rank | `hanjeok:related/<id>`, `hanjeok:place/<id>` each | `concepts/alternative-scoring.md` |
| `congestion` | `place_id` already fetched; `date` today to today+30 | Hanjeok, live | `hanjeok:congestion/<id>@<date>` | `concepts/congestion-diagnosis.md`, `records/congestion/grade-policy.json` |
| `alternatives` | `place_id` already fetched; `date` as above; `radius_km` 1–50 | Hanjeok, live | `hanjeok:alternatives/<id>@<date>`, `hanjeok:place/<id>` each | `concepts/alternative-scoring.md`, `decisions/keep-llm-out-of-ranking.md` |
| `events` | `place_id` already fetched; `date` | graph | `hanjeok:events/<id>@<date>` | none |
| `policy` | `text` 1–200 chars | graph, wiki chunks | `wiki:<path>` for up to 3 | the pages returned |

"Already fetched" means a place the question's scope step resolved or an
earlier lookup in the same question returned. A model cannot reach a place by
guessing its id.

`related_places` is absent from the `vector` strategy. Nothing else differs
between strategies.

An input outside its limits produces a refusal with a reason. The refusal is
returned to the model and recorded as a step; it is not an error.

## Per-question records

### Visit

| Field | Notes |
| --- | --- |
| `visit_id` | Random, issued by the service on the first question, held by the browser tab |
| `turns` | Earlier questions with their resolved place ids and dates. Answer text is not kept as context |
| `expires_at` | 30 minutes after the last question. Held in memory only |

### Step

| Field | Notes |
| --- | --- |
| `index` | Order within the question |
| `kind` | `scope`, `resolve`, or a lookup name |
| `inputs` | As validated. For a refusal, as the model gave them |
| `status` | `ok`, `refused`, `no_data`, `failed` |
| `reason` | Present for `refused` and `failed` |
| `produced` | Citation ids this step added to the fetched set |
| `summary` | Short, display-ready description of what came back |
| `as_of` | For graph lookups, the export time. For live lookups, the fetch time |

### Answer

| Field | Notes |
| --- | --- |
| `outcome` | `answered`, `ask_user`, `declined`, `no_grounds`, `failed` |
| `text` | Present only for `answered` |
| `citations` | Each `{id, kind: record\|policy, label}` |
| `candidates` | Present only for `ask_user`: places to choose among |
| `cause` | Present for every outcome except `answered`. One of `unsupported_topic`, `rule_override`, `off_topic`, `ambiguous_place`, `unknown_place`, `date_out_of_range`, `no_grounds`, `invalid_citations`, `budget_exhausted`, `service_unreachable`, `model_failed`, `usage_limit` |
| `partial` | True when the budget ran out and the answer was given from what was fetched |
| `path` | The places, relationships and documents touched, for the path view |

### Run record

One line per question per strategy in `bench/runs/guide-<id>.jsonl`, with the
fields of the bench run record plus `steps`, `fetched`, `outcome`, `cause`,
`strategy`, `export_sha256`, `generation` and `live_recording`.

## Question set, version 2

`bench/questions/hanjeok-v1.yaml`. Version 1 files remain valid for the bench.

| Field | Notes |
| --- | --- |
| `id`, `version: 2` | |
| `questions[].id` | Unique |
| `questions[].question` | Korean |
| `questions[].kind` | `place_lookup`, `alternatives`, `date_comparison`, `policy`, `multi_place`, `unsupported` |
| `questions[].anchor_date_offset` | Days from the evaluation date, so "this Saturday" resolves the same way in both arms |
| `questions[].needs` | Citation id patterns the answer must rest on, such as `hanjeok:place/1234` or `wiki:concepts/congestion-diagnosis.md`. Empty for `unsupported` |
| `questions[].expect` | `answered`, `declined` or `ask_user` |

Validation: at least 60 questions and at least 8 of each kind (SC-005); every
`hanjeok:` id in `needs` exists in the loaded generation; every `wiki:` path
exists in the wiki corpus.

## Evaluation report

The bench report shape, with these changes: `strategies` has keys `vector` and
`graph`; each has `forbidden` (`{behaviour: {runs, occurrences}}`),
`id_precision` and `id_recall` beside the RAGAS metrics; the report carries
`export_sha256`, `generation`, `live_recorded_at` and `limitations`.

## Export files

Defined in `contracts/hanjeok-export.md`. The graph holds nothing that is not
in those files or in the wiki.

## Design values and character assets

| Entity | Home | Notes |
| --- | --- | --- |
| Design value | `frontend/src/app/globals.css`, `@theme` | Raw scales, then purpose-named values. Components use only the purpose-named ones |
| Character asset | `frontend/public/brand/guide/<state>.webp`, source in `design/guide-character/v1/` | One per state: `waiting`, `looking`, `found`, `choose`, `no-data`, `failed` |
| Provenance record | `design/guide-character/v1/provenance.json`, `prompt.txt` | Fields of Hanjeok's provenance template, plus the tool, prompt, reference inputs, edit steps and SHA-256 of source and output |
