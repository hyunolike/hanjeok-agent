# Research: Hanjeok Guide Agent

Decisions taken before design, each with what was read to reach it. "Read"
means the code or document was opened on 2026-10-13; nothing here was run
unless it says so.

## 1. Where the new code lives

**Decision**: Add a second package, `guide`, to the existing `bench/` Python
project (`bench/src/guide/`). It imports from `bench` and `bench` never imports
from it. `retrieval-service/` and `experiments/retrieval/` are left as they are.

**Rationale**: `bench` already has the pieces the guide needs and has tests for
them: the loader seam (`corpus/loader.py`), the local embedder, the citation
gate, the RAGAS judge and the report writer. Putting the guide in the same
project lets it call them directly. Keeping it a separate package keeps the
bench's two measured arms byte-for-byte unchanged, which Principle II requires:
a change to the guide must not move a number the bench already published.

**Alternatives rejected**:

- *Merge all three Python trees into one.* `retrieval-service` is hard-wired to
  the nine bundle documents and returns hashes that the Kotlin server checks
  against its packaged bundle (`retrieval_service/index.py`, `RetrievalContext.kt`).
  It serves a different consumer under a different contract and runs on Python
  3.12 while `bench` requires 3.13. Merging would touch the deployed Kotlin
  path for no gain to this feature.
- *Rename `bench/` to something product-shaped.* Every published report, the
  constitution and the 001 documents name `bench/`. The rename buys a nicer
  word and breaks those references.
- *Port the Kotlin agent loop.* The constitution forbids porting code from the
  explanation service, and the Kotlin loop is bound to one course.

## 2. Which places are exported

**Decision**: The export contains places that have congestion coverage, plus
places that appear as a related target of a covered place. Each row carries
`has_congestion_data`. Places outside both sets are not exported.

**Rationale**: Hanjeok holds about 260,000 places nationwide and about 10,700
with congestion coverage (`docs/design.md:67`, `README.md:264`). The agent's
questions are about crowding and alternatives, which only covered places can
answer. Related targets are kept so that a relatedness link never points at a
place the agent cannot name. No current row counts are documented for
`derived_related`, so the export manifest reports the counts it produced and
the first real export decides whether a cap is needed.

**Alternatives rejected**: exporting all 260,000 places (embedding time and
graph size grow 25-fold for places the agent can say nothing date-bound about).

## 3. How Hanjeok data crosses over

**Decision**: A directory of JSON Lines files, one per entity, with a
`manifest.json` listing each file's row count and SHA-256, the export time and
the export format version. Produced on the Hanjeok side by a `psql \copy`
script with an explicit column allow-list. See `contracts/hanjeok-export.md`.

**Rationale**: The spec fixes "a file exported on the Hanjeok side". `\copy`
with named columns is the only export precedent in the Hanjeok repository
(`scripts/live-area-forecast-accuracy.sql:73`), and an allow-list means a new
column added to a table later is not exported until someone adds it. The
manifest is the record of what was handed over (SC-009).

**Development does not wait for it**: a small synthetic export in the same
format is committed under `bench/tests/fixtures/hanjeok-export/` and every test
and the local demo run against it. The real export is needed only for the
published evaluation.

## 4. Which Hanjeok endpoints the agent may call

**Decision**: Two, both read-only: `GET /api/v1/attractions/{id}/congestion`
and `GET /api/v1/attractions/{id}/alternatives`. Place lookup, place detail,
relatedness and events are answered from the export.

**Rationale**: `GET /api/v1/attractions/{id}` records a `DETAIL_VIEW` event on
every call (`AttractionController.kt:68`), so calling it would write to the
service and inflate its statistics, which FR-016 forbids. Hanjeok has no rate
limiting (`docs/api-contract.md:1065`), so the demo bounds its own calls
(FR-030) and also caches each live response for the rest of that question.

An uncovered place returns HTTP 200 with `hasCongestionData: false`. That is
the "unknown" of FR-014 and is carried as its own outcome, never as a grade.

## 5. Graph store and search at ten thousand places

**Decision**: Keep Neo4j 5.26. Places get their own label, their own
relationship types and their own vector index, queried through the index
rather than by scanning.

**Rationale**: The bench creates a vector index and never queries it;
`vector_search` scores every chunk of a corpus by exact cosine
(`graph/query.py:51-79`) because Neo4j 5 cannot pre-filter an index by corpus.
A separate `Place` label gives places an index of their own, so no filter is
needed. Relatedness becomes `(:Place)-[:RELATED_TO {rank, score}]->(:Place)`,
directed and ordered by `rank`; the bench's `LINKS_TO` is undirected, has no
properties and is ordered by path, which cannot satisfy FR-008 or FR-023.

**Alternatives rejected**: a separate vector database (a second store to keep
in step with the graph, for a corpus that fits in one); in-memory search
(works, but then "graph retrieval" would not be using the graph).

## 6. Refresh that cannot lose the previous copy

**Decision**: Every place, region, event and relationship carries a
`generation` id. A refresh writes a complete new generation, verifies its
counts against the manifest, then moves one pointer on the `Corpus` node and
deletes the old generation. Every read filters by the active generation.

**Rationale**: The bench's `rebuild` drops then builds (`runtime.py:91-94`), so
a failure leaves nothing, which violates FR-020. With a pointer, a failed
refresh is simply never activated. Vector index results are over-fetched and
filtered by generation, since both generations are in the index for the
minutes a refresh takes.

Embeddings are cached on disk by content hash, so a refresh embeds only places
whose text changed.

## 7. How the model chooses a lookup

**Decision**: The model returns a structured "next action" object whose
`action` field is an enum of the fixed lookups plus `answer` and `ask_user`.
Code validates the arguments, runs the lookup and feeds the result back. Native
tool-calling is not used.

**Rationale**: FR-010 wants a fixed set with validated inputs and a refusal
reason returned to the model. A schema enum makes an unlisted lookup
unrepresentable. This provider path is already proven here: the bench calls
the NVIDIA-hosted model with `json_schema` strict structured output
(`models.py:45-54`). Whether that model supports native tool calls was not
verified, and this decision removes the need to find out.

## 8. What happens before the first model call

**Decision**: Two deterministic steps run first and are streamed immediately:
a scope check (unsupported topics, rule-override phrasing, reference
resolution from earlier questions) and place-name resolution against the
exported names.

**Rationale**: The provider is paced at one request start per three seconds
process-wide (`provider.py:14-51`), and SC-001 requires the first step within
three seconds. Steps that need no model meet it regardless of the queue. The
scope rules already exist and are tested in `experiments/retrieval/guard.py`;
they are re-implemented in `guide` with their own tests, since `bench` cannot
import from a Python 3.12 tree.

Ambiguous names end the request with `ask_user` and a candidate list (FR-015)
without spending a model call.

## 9. Budgets

**Decision**: At most three lookup rounds, one answer call and one repair
call per question, inside a 60-second deadline. When the round or time budget
is spent the next call offers only `answer`.

**Rationale**: Five paced calls fit in 60 seconds with margin. Removing the
lookups from the last call makes "continue" unrepresentable, the same device
the Kotlin `AgentLoop` uses.

## 10. Streaming without leaking unverified text

**Decision**: Steps are streamed as they happen. The answer is produced as one
structured object, verified, and only then sent. It is not token-streamed.

**Rationale**: FR-006 forbids showing unverified text. The Kotlin service
solves this with an incremental parser and a gate; here the answer is short
and the wait is already filled by visible steps, so sending it whole after
verification is simpler and cannot leak.

## 11. Citations of two kinds

**Decision**: A citation is a string with a scheme: `wiki:<path>` for a policy
document, `hanjeok:place/<id>`, `hanjeok:related/<id>`,
`hanjeok:congestion/<id>@<date>`, `hanjeok:alternatives/<id>@<date>` and
`hanjeok:events/<id>@<date>` for records. The gate accepts a citation only if
that exact string was produced by a lookup in this question.

**Rationale**: FR-003 needs the two kinds distinguishable and FR-004 needs
verification against what was fetched for this question. The bench gate checks
document paths against corpus and supplied sets; the guide's gate is the same
check over one set of fetched ids.

## 12. How policy documents reach an answer

**Decision**: Each lookup declares the wiki pages that explain its result
(for example the congestion lookup declares `concepts/congestion-diagnosis.md`).
Those pages are fetched with the result. A separate `policy` lookup searches
the wiki by text for questions that are about the rules themselves.

**Rationale**: The wiki has 18 pages. A declared table is deterministic,
reviewable and cannot miss, where vector search over 57 chunks already missed
the scoring-formula chunk once (`bench/reports/phase3-smoke.md`).

**Changed after the first real evaluation (2026-10-14)**: the `policy` lookup
no longer relies on search alone. Asked "혼잡 등급은 어떻게 나눠?", similarity
search over the English wiki returned three unrelated pages under both
strategies, and the model then cited the page it expected rather than one it
had been given, which the gate refused twice. The lookup now takes the pages a
small keyword table names first and lets search fill the rest. The failing
question was in the set that found it, so the next run's score on that question
is not evidence the fix generalises.

## 13. The two evaluated strategies

**Decision**: `vector` offers place search by text. `graph` offers the same
search plus the relatedness lookup. Everything else is shared: questions,
instructions, model settings, budgets, citation gate, judge.

**Rationale**: FR-026 and Principle II. The bench's `whole` arm cannot exist
here: all passages exceed its 100,000-byte input budget by two orders of
magnitude.

## 14. Evaluating against data that changes daily

**Decision**: Live Hanjeok responses are recorded during an evaluation run
and stored with it. Both strategies answer from the same recording, and the
report is stamped with the recording time.

**Rationale**: Congestion forecasts change every day. Without a recording the
two arms could see different facts, and yesterday's report could not be
reproduced. With one, the pair differs only in retrieval.

## 15. Metrics

**Decision**: RAGAS `Faithfulness`, `AnswerRelevancy`, `ContextPrecision` and
`ContextRecall` as the bench runs them, plus two judge-free measures: id-based
context precision and recall over the citation ids a question is known to
need, and deterministic forbidden-behaviour counts.

**Rationale**: The judge and the answer model are the same model here, a known
limitation of 001. The id-based measures and the counters do not depend on a
judge and give the comparison a floor that cannot be argued with.

Forbidden behaviours and how each is decided:

| Behaviour | Rule |
| --- | --- |
| `INVENTED_PLACE` | A name from the exported gazetteer appears in the answer and its record was not fetched for this question |
| `ALTERED_ORDER` | Alternatives named in the answer are not a subsequence of the order the service returned |
| `LLM_CHOSE` | The phrasing rules of the Kotlin detector, ported |
| `UNCITED_CLAIM` | The answer was withheld by the citation gate |
| `GRADE_MISLABEL` | An enum token or a known mistranslation appears in the answer |
| `NO_DATA_AS_QUIET` | A place whose lookup returned "no data" shares a sentence with a quietness term |

`INVENTED_PLACE` is stricter than the Kotlin rule, which guesses from word
endings. With the gazetteer loaded the check is exact for exported places; a
place Hanjeok does not have at all is not detectable this way and is listed as
a limitation in the report.

## 16. Deployment

**Decision**: The Python service and Neo4j run in one Docker container on a
Hugging Face Space. On start the container imports a prebuilt corpus pack (the
export plus cached embeddings) into Neo4j. The frontend stays on Vercel and
calls the Space.

**Rationale**: The course names Hugging Face Spaces; the frontend already
deploys to Vercel. A Space's disk does not persist, so the graph is rebuilt
from files on every start, which Principle "the graph store is disposable"
already demands.

**Not verified**: that Neo4j runs inside a Space container alongside the
embedding model within its memory, and how long the import takes there. This
is the first deployment task and it is a spike: if it fails, the fallback is a
hosted Neo4j instance, decided then with the measurement in hand.

## 17. Frontend additions

**Decision**: Tailwind 4 `@theme` tokens in `globals.css` in two layers (raw
scales, then purpose-named values), taking Hanjeok's own colour values so the
demo and the product match. Pretendard for text and Wanted Sans for display,
as Hanjeok uses. Shared primitives in `frontend/src/components/ui/`. The path
view is hand-written SVG with a deterministic layout. No UI, animation or graph
library is added.

**Rationale**: The frontend has two CSS variables and no tokens, expresses
hierarchy through opacity, and has no `public/` directory. Hanjeok's values
are in `frontend/src/shared/config/design-system.ts`; reusing them is what
"within the Hanjeok brand" means. A path view shows the few dozen nodes one
answer touched, which does not need a layout engine. The existing screens are
colocated and have no shared component directory; one is added because six new
screens sharing a button and a badge would otherwise copy them.

The grade pills in `grades.ts` have no dark variants and fail FR-038 today;
they move to grade tokens with both appearances.

## 18. Screens work before the service exists

**Decision**: The guide client takes an injectable `fetchImpl`, as
`lib/agent.ts` does. When `NEXT_PUBLIC_GUIDE_BASE_URL` is unset it replays
recorded streams from fixtures.

**Rationale**: The author asked for screens first, and CI builds the frontend
with no backend running. Replay also gives every preview deployment a working
demo.

## 19. The guide character

**Decision**: A leaf scout, working name 잎새: a small leaf-shaped companion
that flies ahead to look and comes back with what it found. Navy outline, the
brand's quiet green `#009C75` as its body colour, a coral ribbon echoing the
sun guide's. Six poses, 512×512 transparent PNG sources exported to 384×384
WebP, generated through Codex image generation with the approved sun guide as
a style reference, each with a prompt file and a provenance record.

**Rationale**: The agent's job is going and fetching, which a scout shows and a
second guide would not. A leaf is already Hanjeok's own mark for quietness. A
non-round, non-gold silhouette cannot be mistaken for the sun guide at small
size. Codex image generation with the sun guide as reference is how Hanjeok's
existing raster assets were made (`source/course-traveler-v1/generation-jobs.json`).

**Released by the author's decision, with the review still not done**:
Hanjeok's own legal review marks its brand assets as blocked for public
release, with trademark and AI-copyright review not done
(`design/brand/review/legal-review.md:34`). A character made inside that brand
by the same method inherits the same status. On 2026-10-14 the author decided
to show the six poses on the public demo and in the public repository anyway.
That decision is recorded in `design/guide-character/v1/provenance.json` under
`releaseDecision`, with `rightsReviewStatus: not-performed` and the open items
listed. It does not change Hanjeok's review document.

Hanjeok's manifest has a single `mascotMaster` object and review checklist
item 3 is written for the sun guide's face geometry. How a second character is
registered there is a Hanjeok-side change and belongs to attaching the agent
to the product, which is out of scope.

## 20. Libraries taken up on 2026-10-14

**Decision**: At the author's direction, four things that were hand-written or
absent are now libraries. None of them changes a boundary in this document.

| Was | Now | What it did not change |
| --- | --- | --- |
| A callback, a thread and a queue to stream steps | LangGraph's custom stream (`get_stream_writer`) | The events and their order |
| Re-sending the question with a `choice`, checked against a set kept beside the visit | LangGraph `interrupt`, resumed with `Command(resume=…)` | The HTTP request still carries `question`, `visit_id`, `choice`; a choice must still be one that was offered |
| A visit's earlier questions in a dict | The visit's thread in a LangGraph checkpointer; in memory, or SQLite with `GUIDE_CHECKPOINT_DB` | Answer text is still not kept; a visit still expires after thirty minutes and its thread is deleted then |
| A hand-written vector-index query with a twenty-fold over-fetch | neo4j-graphrag `VectorCypherRetriever` with `filters` | The Cypher fragment is fixed text. The library's text-to-Cypher retriever is not used: the model does not write queries (Principle VI) |
| No way in for another program | An MCP server (`guide mcp`) with four read-only tools | Refresh and evaluation are still not exposed |
| Run records read by script | Langfuse tracing through LangChain callbacks, off unless its keys are set | Nothing is sent anywhere by default |

**Found on the way**: neo4j-graphrag 1.21.0 cannot run a filtered
`VectorCypherRetriever`. The base class stores the index's embedding property
as `_embedding_node_property`; `VectorCypherRetriever` reads
`_node_embedding_property`, which stays `None`, and the query builder refuses
with "Vector Search with filters requires: …". `guide.graph.read.cypher_retriever`
copies the value across.

Checked on 2026-10-14: this is real and already known. It is upstream issue
#540 (opened 2026-06-07, labelled `bug`, unassigned), a fix is proposed in pull
request #541 (open, unmerged), and the mismatch is still on `main`; the newest
release is 1.22.0. So it is **not** a new issue this project can file. What
remains open to contribute is confirmation that it reproduces on 1.21.0 with
Neo4j 5.26, where the Cypher 25 `SEARCH` path is not taken.

**Not verified**: Langfuse against a real Langfuse server (the wiring is tested
with a plain LangChain callback handler); the MCP server's streamable-HTTP
transport (stdio was called with a real MCP client); whether Spring AI's MCP
client connects to it.

