# Quickstart: Retrieval Bench

Phases 3–5 provide both answer paths, recorded pairs, stored question sets and
scored reports on the existing wiki. Personal worklogs and document-size
sampling are excluded from the current scope.

## Prerequisites

- Python 3.13+, `uv`, and Docker.
- A local checkout of travel-context-wiki, read-only to this subproject.
- `NVIDIA_API_KEY` for answers and judging. Loading and offline tests need no API key.

## Bring it up

From the repository root:

```bash
cd bench
uv sync --locked
docker compose up -d --wait neo4j
export BENCH_WIKI_ROOT="/absolute/path/to/travel-context-wiki"
export NVIDIA_API_KEY="<your NVIDIA API key>"
uv run bench corpus load wiki
uv run bench corpus list
uv run uvicorn bench.api:app --host 127.0.0.1 --port 8100
```

The first load downloads the pinned multilingual model
(`intfloat/multilingual-e5-large`, 1024 dimensions); later loads use its local
cache. Keep the server local. Loading prints counts, revision, and unresolved
links/sources. An empty or mixed corpus is rejected before deleting existing
state. `load` and `rebuild` both replace the old graph so deleted documents do
not remain citable.

Export `NVIDIA_API_KEY` before starting the server, as shown above. If it was
started without the key, restart it after exporting. `.env` is
not loaded automatically. `BENCH_ANSWER_MODEL` and `BENCH_JUDGE_MODEL` default
to `nvidia/nemotron-3-super-120b-a12b`. Both clients use NVIDIA's hosted endpoint
(`https://integrate.api.nvidia.com/v1`), temperature 0 and reasoning off. No
OpenAI or other provider fallback is configured. Local embeddings remain the
same pinned, cached multilingual model that created the graph. External model
calls consume NVIDIA account quota; offline tests make none.

Both strategies use the same conservative input budget. `BENCH_MAX_INPUT_BYTES`
defaults to 100000: system/user UTF-8 bytes, JSON schema bytes, and a 2048-byte
envelope reserve. This is a local input limit, not an estimate of billed tokens
or a discovered provider context window. Configure it for the chosen model;
output tokens also need room in that model's context window. Oversize inputs
return `budget_exhausted` before calling the model, retaining the selected
passages in the run record and never truncating them. Repairs are checked too.

Neo4j defaults: `bolt://localhost:7687`, user `neo4j`, local password
`benchbench`. Override `BENCH_NEO4J_URI`, `BENCH_NEO4J_USER`, and
`BENCH_NEO4J_PASSWORD` together when using another local store.

## Check 1 — an answer names its sources

```bash
curl -s localhost:8100/bench/ask -H 'content-type: application/json' \
  -d '{"question":"대안 목록에는 어떤 혼잡도 등급만 들어가고, 예측 데이터가 없는 후보는 어떻게 되나?","corpus":"wiki","strategy":"graph"}'

uv run bench ask --question "대안 목록에는 어떤 혼잡도 등급만 들어가고, 예측 데이터가 없는 후보는 어떻게 되나?" \
  --corpus wiki --strategy graph --show-supplied
```

Expect `answered`, real document paths, supplied passages, actual token usage
and `corpus_revision`. Open a cited file and check that its text supports the
answer. `--show-supplied` includes the exact text and opaque attributes given to
the model; HTTP lists document/chunk identities and sizes.

## Check 2 — a fabricated citation destroys the answer

```bash
uv run pytest tests/unit/test_citation_gate.py -k fabricated
uv run pytest tests/contract/test_ask_contract.py -k invalid_citations
```

The injected model cites an invented path. After at most one repair, HTTP
returns 422 with `invalid_citations` and **no answer field or rejected text**.
An existing document that was not supplied is also rejected.

## Check 3 — the corpus decides what can be answered

```bash
uv run bench ask --question "경복궁 입장료가 얼마인가?" \
  --corpus wiki --strategy graph --show-supplied
```

The wiki does not cover ticket prices: expect `no_grounds` and `answer: null`.
No passage above the similarity threshold also ends with no grounds without a
model call. There is no fallback to the entire corpus.

## Check 4 — the same question both ways

From `bench/`, with the wiki loaded and key exported:

```bash
uv run bench pair --question-id scoring-weights \
  --question "대안 추천 점수의 세 요소와 가중치는 무엇이며, 검증된 가중치인가?" \
  --corpus wiki --show-diff

uv run bench ask --question "혼잡도 등급은 어떤 값으로 결정되는가?" \
  --corpus wiki --strategy whole --show-supplied

uv run pytest tests/unit/test_arms_share_inputs.py \
  tests/unit/test_pair_validity.py tests/unit/test_pair_cli.py
```

`pair` prints both answers, sources, supplied text, provider token counts, timing
and validity. `--show-diff` adds an audit of the captured first-request inputs:
`shared_equal: true`, with only `supplied` differing (or no differences if both
selections coincide). Model settings and citation/output schema are identical.
Whole supplies all stored chunks without embeddings, ranking or truncation.

`pair` takes explicit question text and ID. `run` below reads both from the
stored question set, avoiding transcription between evaluation runs.
Default artifacts are `runs/pairs-YYYY-MM-DD.jsonl` (UTC) and the companion
`runs/pairs-YYYY-MM-DD.pairs.jsonl`. Use `--runs-file runs/my-pairs.jsonl` to
choose another destination. Runs append and flush after each arm, including
failures. The companion links the two run IDs and records pair validity.
Both files must be empty or end at a newline boundary. An interrupted tail
causes a named failure before any model calls, leaving prior bytes untouched.
The append boundary is also checked under the write lock.

A revision, generation, size, question, model or common-input mismatch makes
the pair invalid, with a cause and a nonzero CLI exit. Missing snapshot/input
metadata also excludes a pair. A same-revision rebuild therefore invalidates
it conservatively. One arm's failure does not prevent recording the other;
failed arms remain visible and the pair is ineligible for future scoring.
`model_calls` distinguishes selected inputs never submitted (zero) from attempted
requests. A zero token count after an exception means no usage was reported;
it is not a claim that the provider did not bill the attempt.
Output-limit failures preserve usage supplied by the SDK and discard partial
answers as `budget_exhausted`.

## Check 5 — linked evidence reaches the answering step

```bash
uv run bench ask --question "혼잡도 등급은 대안 추천 점수에 어떻게 반영되나?" \
  --corpus wiki --strategy graph --show-supplied
uv run pytest -m integration tests/integration/test_retrieval.py
```

Inspect seed passages and `expanded: true` entries. Expansion follows one hop
of document links, shared sources or shared tags, deduplicates documents, and
supplies title plus a first-sentence excerpt (at most 240 characters), with
attributes copied intact. Integration tests prove all three edge types and
that a second-hop document does not leak into results.

## Check 6 — unattended evaluation and applicable scores

The full hosted commands below document an optional evaluation flow. Repeated
hosted evaluation is excluded from the current completion scope by the user;
the offline evaluation tests and saved-report reading still apply.

```bash
uv run bench run --question-set wiki-v1 --corpus wiki
uv run bench report --id <report-uuid>

curl -s localhost:8100/bench/run -H 'content-type: application/json' \
  -d '{"question_set":"wiki-v1","corpus":"wiki"}'
curl -s localhost:8100/bench/reports/<report-uuid>

uv run pytest tests/unit/test_evaluation.py tests/unit/test_evaluation_interfaces.py
```

CLI `run` waits for completion. HTTP returns 202 with a report ID/status URL;
polling shows answering or scoring progress until the completed report is
available. A single worker queues evaluations within a server process. Saved
running markers read by a fresh HTTP service become `interrupted`; jobs do not
resume automatically. CLI `report` reads JSON without constructing a runtime.
For a saved running marker it returns `status: unknown`, `saved_status: running`
and exit 1, because an offline reader cannot establish whether the original
server is still alive. Query that server's status URL for live progress.

Question files live in `bench/questions/`. Their exact YAML bytes determine a
SHA-256 revision. References must name loaded canonical documents; invalid
questions fail before model calls. `must_contain` contains factual reference
clauses for RAGAS, not literal substring assertions.

Reports are `reports/<uuid>.json`; answer, pair and score observations are
`runs/<uuid>.jsonl`, `.pairs.jsonl` and `.scores.jsonl`. Each observation is
flushed before progress advances. A failed answer continues to the next arm and
question; a failed judge leaves a null score and fixed cause. Artifact failures
stop the job, immediately cancel sibling scoring tasks and await their cleanup
before closing the provider client. Corpus generation, size, model and common inputs must match the
frozen profile to enter scoring.

Both arms receive answer faithfulness and relevancy scores when they answer.
Faithfulness judges only the actually supplied passages from cited documents,
including attributes. Graph receives context precision and recall against
reference clauses. Whole's retrieval metrics are `not_applicable` with a reason,
`value: null`, `n: 0`. Declines have no numeric answer scores. Every aggregate
carries its successful sample count, failures and skipped observations; outcomes
and unsupported-question abstention accuracy keep all requested denominators.
Results also split by question kind. Do not compare means without their counts.

The judge uses RAGAS 0.4 collections, local query embeddings for answer
relevancy, no response cache, one structured attempt, four concurrent metric
jobs and a shared three-second default interval between NVIDIA request starts.
`BENCH_REQUEST_INTERVAL_SECONDS` changes that interval; it is process-wide,
not a cross-process quota coordinator. Waiting consumes the answer deadline.
A metric has a ten-minute limit and each request a 90-second timeout. Full runs
can take many minutes. Absent `sizes` or the one current full size is accepted;
sampling and multiple sizes return 409 and are outside the current scope.

Failures retain sanitized error categories and HTTP status when available.
Per-run JSON logs go to stderr and omit question, answer and context bodies.

## Check 7 — rebuilding reproduces retrieval

```bash
uv run bench corpus rebuild wiki
uv run pytest -m integration tests/integration/test_retrieval.py \
  tests/integration/test_runtime.py
```

Same files and model revision produce the same passage ordering, with ties
ordered by document path and chunk ID. Deleted documents and their edges must
disappear. Compare `supplied` lists, not model wording, which may vary.

Neo4j 5 cannot pre-filter the shared ANN index by corpus. This implementation
uses **exact cosine ranking within the selected corpus**, avoiding another
corpus's hits starving this one's top-k. Its latency is not an ANN measurement.

## Tests and later milestones

```bash
uv run pytest                         # offline unit and HTTP contract tests
uv run pytest -m integration          # local Neo4j, fake models, no API key
uv run ruff check src tests
uv run ruff format --check src tests
```

Document-size sampling and crossover measurement are out of scope.
Earlier Phase 3–4 smoke
artifacts used OpenAI models; they are historical evidence and are not mixed
with the NVIDIA Phase 5 comparison.
