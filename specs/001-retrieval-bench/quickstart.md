# Quickstart: Retrieval Bench

Phases 3–4 provide both `graph` and `whole` answer paths, corpus discovery,
clean rebuilds and recorded pairs. Stored question sets, scoring and size
curves belong to Phases 5–6 and are not yet implemented.

## Prerequisites

- Python 3.13+, `uv`, and Docker.
- A local checkout of travel-context-wiki, read-only to this subproject.
- `OPENAI_API_KEY` for answers. Loading and offline tests need no API key.

## Bring it up

From the repository root:

```bash
cd bench
uv sync --locked
docker compose up -d --wait neo4j
export BENCH_WIKI_ROOT="/absolute/path/to/travel-context-wiki"
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

Before asking, export `OPENAI_API_KEY` in the server's environment. The root
`.env` is not loaded automatically. `BENCH_ANSWER_MODEL` defaults to `gpt-4o`.
Answering calls a paid model; offline tests do not.

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

`--question` is required until Phase 5 implements stored question-set lookup;
the supplied ID identifies this exact question, rather than fetching text yet.
Default artifacts are `runs/pairs-YYYY-MM-DD.jsonl` (UTC) and the companion
`runs/pairs-YYYY-MM-DD.pairs.jsonl`. Use `--runs-file runs/my-pairs.jsonl` to
choose another destination. Runs append and flush after each arm, including
failures. The companion links the two run IDs and records pair validity.
Both files must be empty or end at a newline boundary. An interrupted tail
causes a named failure before any paid calls, leaving prior bytes untouched.
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

Check 6 (RAGAS scores) is Phase 5; check 8 (the size curve and crossover) is
Phase 6. Their CLI/API routes will be documented when implemented. A bounded
pair smoke is not a scored comparison or evidence that either strategy wins
across the corpus.
