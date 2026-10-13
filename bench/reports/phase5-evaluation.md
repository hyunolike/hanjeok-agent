# Phase 5 NVIDIA evaluation

Scope: T034–T043 on `feat/graphrag-bench`, starting at `d521fe0`.
Implementation commit: `746a746`; final review fixes: `c5c33cf`.
Two full external evaluations completed on 2026-10-11 UTC (2026-10-12 KST).
The functionality is verified. The original full-set repeatability criterion
remains **inconclusive**, because the second execution lost samples to provider
failures. This is not a claim that the 0.05 tolerance passes.

## Implementation and profile

Question sets validate shape, unique IDs and loaded canonical references before
inference. Their revision is the SHA-256 of exact YAML bytes. Every question
runs both arms, including failed attempts. The service freezes revision,
generation, size and answer model settings; incompatible pairs stay artifacts
but do not enter scoring. Reports show successful metric counts, skipped and
failed observations, all outcomes, abstention accuracy and splits by kind.

HTTP `/bench/run` returns 202 and a status URL for answering/scoring progress.
Reports are atomic JSON, with append-only answer, pair and score observations.
`bench run` uses the same service; `bench report --id <uuid>` reads saved JSON
without initializing a database or model.

- Corpus: travel-context-wiki `e7f4b44`, 14 documents / 57 chunks.
- Loaded generation: legacy marker `2026-10-11T13:01:49.204468+00:00`;
  no rebuild between repeats.
- [wiki-v1](../questions/wiki-v1.yaml): 18 single-document, 7 multi-document,
  5 unsupported questions. Revision:
  `sha256:9862e9241a9b6cc331d8b1eb3027c2b7f1e43ed997dc85526a471430427d8335`.
- Answer and judge: `nvidia/nemotron-3-super-120b-a12b` at NVIDIA's hosted
  endpoint, temperature 0, reasoning off. Maximum 800 answer / 4096 judge tokens.
  Only `NVIDIA_API_KEY` is used; no OpenAI or other provider fallback exists.
- Local embeddings: `intfloat/multilingual-e5-large`, pinned revision
  `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3`, CPU, normalized 1024 dimensions.
  Relevancy uses query prefixes for original and generated questions; no hosted
  embedding requests are made.
- Whole supplies all stored chunks in stable order, full text and attributes.
- Graph uses corpus-prefiltered exact cosine, top 5 / threshold 0.75, one-hop
  expansion up to 8 documents, title/first-sentence excerpt capped at 240 chars.
- Shared prompt/schema/citation gate, a maximum of two answer attempts within
  the 60-second answer budget, common
  100,000-byte input budget including schema and envelope reserve. No truncation.
- RAGAS 0.4.3 collection metrics, three generated relevancy questions, no
  response cache, one structured attempt, zero SDK retries. Four metric jobs,
  two-second minimum judge-request interval, 90-second request and ten-minute
  metric timeout.

Faithfulness uses only actually supplied passages from cited documents,
including attributes, in both arms. Relevancy uses the question and answer.
Graph precision/recall use all ordered supplied contexts and reference clauses
from the question file. Whole precision/recall are `not_applicable`, with null
value, zero samples and a reason. Declines have no numeric answer score.
All requested outcomes and unsupported abstention accuracy retain their
denominators; means must be read together with sample counts.

## Execution evidence

Actual local Neo4j and NVIDIA models run through HTTP 202/polling, twice in one
process without changing questions, corpus, retrieval, prompt, model or scoring
policy. The local embedder is warmed before both. Offline CLI reads are checked
against the HTTP report.

Reports and their full underlying evidence:

- [First report](f4f07d1c-d621-4317-95eb-cfa8962cd5e8.json), completed
  `2026-10-11T15:16:57.242460+00:00`: [60 arms](../runs/f4f07d1c-d621-4317-95eb-cfa8962cd5e8.jsonl),
  [30 pairs](../runs/f4f07d1c-d621-4317-95eb-cfa8962cd5e8.pairs.jsonl),
  [240 metric observations](../runs/f4f07d1c-d621-4317-95eb-cfa8962cd5e8.scores.jsonl).
- [Second report](18a8e450-5b4d-4557-b15b-5b3dc02581d1.json), completed
  `2026-10-11T15:29:42.596043+00:00`: [60 arms](../runs/18a8e450-5b4d-4557-b15b-5b3dc02581d1.jsonl),
  [30 pairs](../runs/18a8e450-5b4d-4557-b15b-5b3dc02581d1.pairs.jsonl),
  [240 observations](../runs/18a8e450-5b4d-4557-b15b-5b3dc02581d1.scores.jsonl).

| Execution | Arm | Answered / declined / failed | Included pairs | Faithfulness (n) | Relevancy (n) |
| --- | --- | --- | --- | --- | --- |
| 1 | whole | 23 / 7 / 0 | 30 | 0.959369 (23) | 0.915708 (23) |
| 1 | graph | 21 / 9 / 0 | 30 | 0.923016 (21) | 0.902891 (21) |
| 2 | whole | 20 / 4 / 6 | 21 | 0.937500 (12) | 0.927259 (12) |
| 2 | graph | 20 / 4 / 6 | 21 | 0.944444 (12) | 0.905725 (11) |

First-run graph context precision was 0.680698 (n=25), recall 0.940000 (n=25).
Whole's retrieval cells are null/NA in both reports. First-run single-document
faithfulness was 0.949405 whole / 0.927083 graph (both n=16); multi-document
faithfulness was 0.982143 (n=7) / 0.910000 (n=5). These means have different
answer cohorts and are not a standalone strategy-winner test. Both correctly
declined all five unsupported questions in the first run. Both cited the
expected single-document reference for 16/18 questions; graph supplied every
reference path for 6/7 multi-document questions. This is per-question-set
coverage, not the ten repeated trials per question required by SC-001/SC-003.

All 30 first-run pairs have equal common captured inputs, with only `supplied`
differing, and all corpus/model profile stamps match. There were 60 model
attempts with no repair. Whole used 309,573 input / 2,210 output tokens; graph
used 70,648 / 2,175. Graph supplied **77.18% fewer reported input tokens** here,
without establishing a price or quality advantage. First judging used 569
requests with reported usage 748,265 input / 57,988 output tokens, no failures.

The second execution made all 60 arm attempts, including 12 failed model calls,
and conservatively excluded nine pairs. It produced 44 failed judge
observations; remaining means therefore use reduced, different samples. Judge
usage recorded 344 requests, 300 responses with usage (381,597 / 28,300 tokens)
and 44 calls without usage. Unknown usage is not zero billing. Raw provider HTTP
status was not retained by the fixed-cause adapter, so quota, availability and
transport causes cannot be distinguished retrospectively. A later
[one-request NVIDIA health check](../runs/phase5-nvidia-health.json) succeeded;
that does not prove why the earlier requests failed. No paid-provider fallback
or hidden retries were used.

## Repeatability result

The [full comparison](phase5-repeatability.json) deliberately returns
`comparable: false`, `passes: null`: model/corpus/question/policy stamps are
identical, but sample membership differs and the second report has judge
failures. It must not pass by comparing means with different denominators.

A separate [partial-cohort diagnostic](phase5-partial-variance.json) compares
only questions successfully scored in both executions. Its maximum mean delta
is **0.0096484774**, below 0.05, with just 11–14 questions per applicable metric.
All of those intersections are single-document questions; no multi-document
repeat score survives. This diagnostic does **not** verify the full-set
criterion and cannot justify relaxing its tolerance. The specification retains
0.05, adds clean/matching-sample preconditions and records this inconclusive
observation. Phase 6 crossover claims remain gated on a clean calibration.

The next measurement should first control NVIDIA answer-call pacing and
capture sanitized provider status, then repeat under an available quota window.
This report does not assert that rate limiting caused the observed failures.

A [transport probe](../runs/phase5-nvidia-probe.json) exercised NVIDIA structured
answer output and all four RAGAS metrics on an earlier context fixture. It made
19 judge requests. That historical answer is only a judge input, not a new
NVIDIA comparative sample; the probe is excluded from repeat reports.
No Phase 5 OpenAI call was executed. Phase 3–4 OpenAI artifacts are historical
and are not pooled with this NVIDIA profile.

## Verification before final review

116 offline tests / 27 actual Neo4j integration tests passed; Ruff lint/format
passed. Coverage includes escaping/invalid questions, exact hash changes,
reference preflight, failed-arm continuation, frozen-profile exclusions,
decline denominators, not-applicable metrics, nonfinite judges, HTTP progress,
saved report recovery, offline CLI reads, NVIDIA endpoint/key selection and
single-attempt quota failures with unknown usage. Actual probes establish
NVIDIA compatibility independently of offline transport fakes.

One independent read-only review found an Important persistence failure:
`asyncio.gather` let sibling judge tasks start 16 further calls after the score
writer failed. A regression reproduced that behavior before the fix. The
failing observation now immediately cancels siblings; supervision awaits all
cleanup before the client closes. The regression now confirms zero later calls
and zero active siblings when the error returns.

The review labelled CLI orphan status Minor. It was regraded Important because
an offline crash inspection could indefinitely claim a dead job was running.
A second regression failed before the fix. Offline running markers now return
`unknown`, preserve `saved_status: running` and advise checking the original
server. This also avoids claiming that a still-running job in another process
has stopped. Completed reports remain identical across CLI/HTTP. Both regression
tests passed after the one fix pass, with 118 offline tests passing afterwards.
No second reviewer is used. Final verification: **118 offline tests / 27 actual
Neo4j integration tests passed**, with Ruff lint/format passing. No Critical,
unresolved Important or deferred Minor review findings remain.

Actual repeats began before this final error-handling fix pass, in one process
that uses the same loaded implementation for both. Neither trigger occurred
in the measured execution; the fixes do not change its successful scoring path.

## Decisions and limits retained

| Decision | Reason and cost if wrong |
| --- | --- |
| Approved Spec Kit plan inline, track T IDs directly | Skill helper headings differ; manual bookkeeping can drift. |
| Joined reference clauses and exact file hash | Reviewable content identity; human claim errors affect retrieval scores. |
| Faithfulness restricted to supplied cited contexts | Uncited support cannot rescue claims; stricter than all-context RAGAS. |
| Declines have no answer score, outcomes/abstention separate | Absent answers are not numerically graded; no single overall success score. |
| Frozen revision/generation/size/model and pair exclusions | Avoid mixed inputs; identical rebuilds and some failed pairs are conservatively excluded. |
| Full corpus until Phase 6 | Sampling is not pretended; no crossing-point evidence exists. |
| NVIDIA-only inference and authorized credential reuse | User direction; quota/availability and self-judge bias remain. Credentials are ignored local configuration. |
| Existing pinned local embeddings | Preserve the graph without hosted calls; semantic relevance depends on this embedding. |
| Atomic JSON instead of planned YAML | Same API/CLI representation; hand-editing reports is unsupported. |
| Explicit ID/text for pair; stored lookup for run | Sets avoid transcription; standalone pair still needs text. |
| One local worker, no auto-resume | Honest persisted results; multi-process status routing and crash resumption are unsupported. |
| Temperature 0 and requested model alias | Common settings; deterministic provider internals and vendor-optimal sampling are not established. |

## Review behaviors explicitly retained

| Considered behavior | Ruling and cost if wrong |
| --- | --- |
| Sampling/multiple sizes | Phase 6, reject now; no size curve in this result. |
| Distributed workers/cross-process ownership | Local one-worker scope; status routing needs extension before multiple servers. |
| Automatic execution resume | Not implemented; an interrupted run needs a new evaluation, preserving old artifacts. |
| Cancellation endpoint/immediate shutdown | Not added; shutdown can wait for active work. Fatal-persistence cancellation is now verified. |
| Provider/quota retries | Keep zero SDK retries/one structured attempt; transient failures can reduce scored samples. |
| Zero scores for declines or unsupported retrieval | Keep null/not-applicable policy and all outcomes; no invented numeric score for missing inputs. |
| Faithfulness on uncited/unsupplied material | Exclude it; incomplete citations can lower otherwise supported-answer scores. |
| Comparing arbitrary software/prompt/retrieval changes | Outside unchanged-code calibration; the helper does not prove cross-version equivalence. Both repeats use one loaded implementation. |
| Power-loss guarantees beyond atomic replacement | No filesystem crash-consistency guarantee; recovery may need preserved artifacts/backups. |
| Hosted quality/determinism claims | Only measured runs support findings; a small same-model judge sample cannot prove general quality or determinism. |
| T043 actual repeat evidence | Keep completion gated on both reports and variance; implementation tests alone do not establish repeatability. |

Answer and judge use the same model: scores are not independent human validation.
This small curated wiki cannot establish a production retrieval winner or size
crossing point. Answer timing uses the existing pipeline boundary, excluding
some HTTP/runtime overhead. Judge usage is separate; no price estimate is made.
