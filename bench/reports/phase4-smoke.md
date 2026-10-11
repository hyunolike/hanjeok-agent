# Phase 4 pair smoke evidence

Executed 2026-10-11 on `feat/graphrag-bench`, starting from `8ac90fa`.
The implemented scope is T028–T033: whole-corpus selection, append-only run
records, validity/input auditing and `bench pair`. Phase 5 question sets and
scoring are still pending. This is a three-question smoke, not an aggregate
quality evaluation or proof that either strategy wins across the corpus.

## Profile and artifacts

- Corpus: travel-context-wiki, revision `e7f4b44`, 14 documents / 57 chunks.
- Whole: all 57 stored chunks, stable document/ordinal order, full text/attributes.
- Graph: exact cosine within corpus, top 5 / threshold 0.75, one-hop expansion
  of at most 8 documents with first-sentence excerpts capped at 240 characters.
- Embedding: pinned local multilingual-e5-large used for this corpus and query
  selection, same revision as the [Phase 3 report](phase3-smoke.md).
- Model: `gpt-4o`, temperature 0, maximum 800 output tokens, same shared
  prompt and JSON schema. Requested model identity/settings are recorded; the
  unversioned model alias does not establish reproducibility of provider internals.
- Common budgets: 2 provider calls / 60 seconds, input 100,000 UTF-8 bytes
  including schema and a 2,048-byte envelope reserve. This is a conservative
  configurable local limit, not exact tokenizer counting or context discovery.

[Six run rows](../runs/phase4-2026-10-11.jsonl) retain first-request inputs,
full selected context, sources, outcome, actual usage, timing and call count.
[Three pair rows](../runs/phase4-2026-10-11.pairs.jsonl) link run IDs, validity
and the diff. The CLI itself executed these pairs through the actual local
Neo4j store and paid model. All pairs are valid and all captured initial inputs
differ only in `supplied`; each arm made one model call and no repairs.

The existing corpus predates UUID generation records. `corpus_generation` is
its legacy `loaded_at` marker (`2026-10-11T13:01:49.204468+00:00`) in all six
records; a rebuild replaces this with a new UUID. No rebuild occurred during
these pairs.

## Observed results

| Question ID | Question | Whole outcome | Graph outcome | Whole input/output tokens | Graph input/output tokens |
| --- | --- | --- | --- | --- | --- |
| phase4-smoke-01 | 대안 추천 점수의 세 요소와 가중치는 무엇이며, 검증된 가중치인가? | answered | no_grounds | 10,050 / 96 | 2,427 / 16 |
| phase4-smoke-02 | 혼잡도 등급이 장소 선택과 방문 시각에 각각 어떤 역할을 하는가? | answered | answered | 10,047 / 277 | 2,739 / 179 |
| phase4-smoke-03 | 경복궁 입장료가 얼마인가? | no_grounds | no_grounds | 10,037 / 16 | 2,696 / 16 |

For question 1, whole named relatedness, quietness and distance with weights
0.4 / 0.4 / 0.2, explicitly saying they are provisional and unvalidated. This
matches `concepts/alternative-scoring.md`. Graph reproduced the Phase 3 miss:
it selected 10 passages but did not supply the formula paragraph, and declined.
Whole therefore supplied the missing evidence for this particular question.

For question 2, both answers distinguished congestion-based place selection
from travel-time-based visit ordering/times. Both cited alternative scoring and
course generation; graph also cited congestion diagnosis. Manual inspection
found support for the returned claims. This is not independent judge scoring.
For question 3, both correctly declined the ticket-price question, which the
wiki does not cover.

Total reported input/output tokens for these three questions were 30,134 / 389
for whole and 7,862 / 211 for graph. Lower usage here is not proof of better
quality or total monetary cost. Whole always ran first, and the first graph
request loaded the local embedding model; recorded latency includes that cold
start. This smoke does not establish a latency advantage for either strategy.

## Validation and next milestone

Before final review, **84 offline tests** and **26 actual Neo4j integration
tests** passed; Ruff lint/format passed on all 38 Python files. Tests cover all
chunks and attributes, no query embeddings for whole, shared input/schema/budget,
oversize and repair rejection before submission, failed-arm persistence,
append preservation, and revision/generation/model/question/input mismatches.
A regression also verifies that a DB check failing after an answer discards
the answer while preserving billed usage for the run record.

A separate read-only reviewer found two Important issues. Native SDK parsing
on an output-length finish discarded available billed usage; it now returns
`budget_exhausted` with the completion's usage and no partial answer. An
interrupted JSONL tail could corrupt the next run; both artifact files are now
checked before calls and the boundary is rechecked under the append lock.
Incomplete tails are rejected without modifying existing bytes. Four regression
cases failed before these fixes and passed afterwards. Final verification:
**88 offline tests / 26 actual Neo4j integration tests passed**, with no Critical,
unresolved Important or deferred Minor review findings. The paid smoke above
preceded this error-handling fix pass; neither error occurred in those six calls.

Phase 5 (T034–T043) adds stored question sets, unattended execution and RAGAS
scoring with sample counts and metric applicability. Repeatability and aggregate
quality must be measured there before drawing a corpus-wide conclusion.

## Decisions carried into implementation

- Used the existing approved Spec Kit plan and tracked its T IDs directly;
  the execution skill's scripts use a different heading format. The cost is
  manual progress bookkeeping.
- Required `--question` alongside `--question-id` until Phase 5 lookup exists.
  The cost is an extra CLI argument; the record verifies question text too.
- Used the same conservative byte budget in both arms without a tokenizer
  download. It may reject some prompts that a provider could fit; the exact
  local limit is recorded and there is no truncation.
- Checked generation, size and common inputs beyond git revision. The cost
  is conservative exclusion after a same-revision rebuild, protecting against
  comparing different loaded content under one revision.

## Review decisions retained

The review also considered the following behaviors. Each is retained for the
stated reason; costs identify what this implementation does not establish.

| Behavior | Decision and cost if wrong |
| --- | --- |
| Conservative UTF-8 budget | Keep the declared common limit; some provider-fitting prompts may be rejected. |
| Repair inputs absent from initial-input diff | Audit initial inputs and use shared repair logic; this does not prove repaired requests are identical when model responses differ. |
| Failed pairs excluded from scoring | Retain failures and exclude scoring eligibility; Phase 5 must report failures with their denominator rather than hide them. |
| Missing snapshot metadata on early retrieval failure | Exclude the pair conservatively; some same-corpus failed attempts cannot be compared. |
| Same-revision rebuild invalidation | Keep the generation rule; identical rebuilds are also excluded. |
| Requested model alias instead of resolved provider version | Record the requested identity/settings and limit provenance claims; a future alias update can affect repeatability. |
| Injected chat configuration beyond recorded settings | Supported CLI exposes the captured model selection and fixed settings; extending custom model configuration requires extending provenance. |
| Whole-first order and cold initialization | Keep the bounded smoke, make no latency claim; order and cold-start effects remain unmeasured. |
| Pipeline timing instead of full CLI/runtime overhead | Keep the shared existing boundary; recorded time is not complete end-to-end latency. |
| Append/fsync failure stops subsequent work | Fail loudly when evidence cannot be saved; the comparison may end after only one arm. |
| Companion write failure after run persistence | Fail loudly and retain run rows; validity metadata may be absent until investigated. |
| Abrupt termination before any run append | No crash-recovery guarantee; such an in-flight call may not have a persisted result. Interrupted existing tails are now rejected before reuse. |
| Semantic grounding beyond supplied citation membership | Keep citation validation and manual smoke inspection; aggregate faithfulness awaits Phase 5. |
| Whole standalone HTTP/CLI | Retain the tested shared runtime path; this proves the local interface, not deployed service behavior. |
| Phase 5 lookup/scoring and size curves | Keep T028–T033 scope; no aggregate scores or crossover finding exists yet. |
| Earlier pending ledger lines | Retain chronological entries with final completion evidence; the durable task checklist and report describe the final state. |
