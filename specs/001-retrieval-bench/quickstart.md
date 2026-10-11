# Quickstart: Retrieval Bench

Phase 3 provides the `graph` answer path, corpus discovery, and clean rebuilds.
The `whole` comparison, stored question sets, scoring and size curves belong to
Phases 4–6 and are not yet implemented. Asking for `whole` returns a named
failure rather than silently using another strategy.

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

Check 4 (same question both ways) is Phase 4; check 6 (RAGAS scores) is Phase 5;
check 8 (the size curve and crossover) is Phase 6. Their CLI/API routes will be
documented when implemented. Phase 3 makes no claim that retrieval wins.
