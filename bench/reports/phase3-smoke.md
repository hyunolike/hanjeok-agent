# Phase 3 implementation and smoke evidence

Executed on 2026-10-11 on `feat/graphrag-bench`, starting from `3454229`.
Phase 3 (T017–T027) is implemented. This report records a bounded smoke test,
not a comparison of retrieval against whole-corpus prompting or a quality score.

## Implemented path

HTTP and CLI load/rebuild a corpus, select corpus-scoped passages, expand one
graph hop, and use one shared LangGraph answer/prompt path. A citation must name
an existing document supplied to the model. Any invalid citation discards the
whole answer; only one repair is allowed. No grounds yields a null answer.
Call and time budgets, actual provider usage, isolated request checkpoints,
and revision/generation checks during rebuild are covered by regressions.

## Execution profile

| Item | Value |
| --- | --- |
| Corpus | travel-context-wiki, revision `e7f4b44` |
| Loaded size | 14 canonical documents, 57 heading chunks, 0 dropped references |
| Embedding | `intfloat/multilingual-e5-large`, CPU, normalized 1024 dimensions |
| Embedding revision | `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3` |
| Retrieval | Corpus-filtered **exact cosine**, top 5, minimum score 0.75 |
| Expansion | One hop via links/shared sources/shared tags, at most 8 documents |
| Expansion text | Title and first-sentence excerpt, at most 240 characters |
| Answer model | `gpt-4o`, temperature 0, maximum 800 output tokens |
| Request budget | At most 2 model calls and 60 seconds |

Exact ranking is an explicit change from the draft ANN implementation: Neo4j 5
cannot pre-filter the shared ANN index by corpus. Filtering global top-k after
the search can omit relevant hits from the selected corpus. This profile's
latency must not be described as ANN performance. The actual canonical document
count also differs from the draft's assumed 17 documents.

## Paid smoke results

Both artifacts retain all 11 outcomes, question text, references, supplied
passages and attributes, provider token counts, timing, and model/retrieval
settings. The rerun additionally records the shared system prompt's SHA-256.
These are temporary smoke records; the formal Phase 4 runner is still pending.

| Attempt | Known questions answered / asked | Known questions declined | Invalid citations | Unsupported question declined | Input / output tokens |
| --- | --- | --- | --- | --- | --- |
| [Initial](../runs/phase3-2026-10-11.jsonl) | 0 / 10 | 1 | 9 | 1 / 1 | 51,020 / 1,682 |
| [After prompt correction](../runs/phase3-2026-10-11-rerun.jsonl) | 9 / 10 | 1 | 0 | 1 / 1 | 28,816 / 833 |

The initial model responses copied chunk IDs such as `document.md#2` into
document citations. The strict gate rejected them, including after repair.
The correction explicitly requires copying `supplied[].doc` in the shared
prompt and output schema. Validation remains strict; it does not strip fragments
or accept paths that were not supplied. The rerun required no repairs.

The unsupported question was “경복궁 입장료가 얼마인가?” and correctly returned
`no_grounds`. Every citation in the nine accepted responses names a supplied
document. Manual inspection found support for the returned claims, but this is
not an independent faithfulness evaluation. Question 8 only restated the
documented division of responsibility between backend and LLM; its explanation
of the reason was shallow, so `answered` does not imply a complete answer.

The remaining known-answer miss was “대안 추천 점수의 세 요소와 가중치는 무엇이며,
검증된 가중치인가?” The formula is in `concepts/alternative-scoring.md`, but its
chunk ranked 20th in a diagnostic search. The first five hits concerned the
explanation-model decision, and graph expansion's short excerpt omitted the
formula. The model appropriately declined on those supplied passages. No
retrieval settings were tuned to erase this failure, and there is no whole-corpus
fallback. The smoke therefore does not establish that all known questions can
be answered by this profile.

## Automated verification

- Offline suite: **61 passed**, 19 integration tests deselected.
- Actual local Neo4j suite, fake embedding/chat providers: **19 passed**,
  61 offline tests deselected.
- Ruff lint and format checks passed for all 32 Python files.
- Regression coverage includes fabricated/unsupplied/fragment citations,
  corpus isolation, bounded one-hop expansion, reproducible rebuild ordering,
  HTTP/CLI failure shapes, opaque attributes, same-revision rebuild detection,
  malformed/refused response usage, deadline expiry, and diagnostic path redaction.

A separate read-only review found rebuild visibility and lost billed usage
issues; both were reproduced and fixed. Deadline enforcement and diagnostic
path handling were also strengthened with failing-then-passing regressions.

## Remaining scope and decisions

The next milestone is Phase 4 (T028–T033): implement `whole`, store formal run
records, pair by corpus revision, prove shared inputs, and expose `bench pair`.
That comparison can measure the retrieval miss above without changing the
current profile mid-run. Until then, `whole` returns an explicit unavailable
strategy result. Question sets/RAGAS scoring, work-log loading, size curves,
production throughput/deployment, and a full legacy-loader audit remain outside
this implementation. No comparative quality or production latency claim is made.

A local embedding adapter and runtime were added to make the approved CLI usable
with real data; the cost is a larger dependency/model download. Citation checks
also require supplied-document membership, which deliberately rejects an
existing but unseen source. The Spec Kit T IDs were tracked directly because
the execution skill's task scripts expect a different heading format. The
quickstart now uses implemented commands and marks future checks separately.
