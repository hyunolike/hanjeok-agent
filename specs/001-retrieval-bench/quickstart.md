# Quickstart: Retrieval Bench

How to bring it up and confirm it does what the specification says. Every step
below is a check someone else can repeat; none of them require reading the code.

## Prerequisites

- Python 3.13 and `uv`
- Docker, for Neo4j
- An API key for the answering and judging model, exported in the environment
- Both corpora checked out locally, paths given to the loader by configuration

Graph build and unit tests need no key. Answering and scoring do, because they
call a model.

## Bring it up

```bash
cd bench
docker compose up -d neo4j       # graph + vector index
uv sync
uv run bench corpus load wiki    # parse, chunk, embed, write graph
uv run bench corpus load worklog
uv run uvicorn bench.api:app --port 8100
```

`corpus load` prints document, chunk and edge counts, and every link or source
that did not resolve. Unresolved references are expected in a real corpus and do
not fail the load — seeing the list is the point.

## Check 1 — an answer names its sources (User Story 1)

```bash
curl -s localhost:8100/bench/ask -H 'content-type: application/json' \
  -d '{"question":"대안 점수는 어떻게 계산되나?","corpus":"wiki","strategy":"graph"}'
```

Expect `outcome: answered`, `citations` naming real paths, and `supplied`
listing the passages. Open a cited file and confirm the claim is in it.

## Check 2 — a fabricated citation destroys the answer (SC-002)

Point the validator at an empty corpus and ask anything, or run the injected
test that forces a made-up path.

```bash
uv run pytest tests/test_citation_gate.py -k fabricated
```

Expect `422` and `outcome: invalid_citations`, and expect the response body to
contain **no answer text**. An answer that reached a reader with an invented
citation is the one failure this subproject may not have.

## Check 3 — the corpus decides what can be answered

```bash
curl -s localhost:8100/bench/ask -H 'content-type: application/json' \
  -d '{"question":"경복궁 입장료가 얼마인가?","corpus":"wiki","strategy":"graph"}'
```

Expect `outcome: no_grounds` with `answer: null`. Nothing in the wiki covers
ticket prices; a confident answer here means the model is answering from
training data and the grounding is decorative.

## Check 4 — both arms differ only in supplied passages (Principle II)

```bash
uv run bench pair --question-id wiki-007 --corpus wiki --show-diff
```

Prints both runs and diffs their inputs. Expect the diff to touch `supplied` and
nothing else — not the question, not the instructions, not the model settings.
**This is the check most worth re-running after any prompt change**, because a
violation here invalidates every number the subproject has produced, and it will
look like an improvement to one arm when it happens.

## Check 5 — a multi-hop question pulls in the linked document (SC-003)

```bash
uv run bench ask --question-id wiki-012 --strategy graph --show-supplied
```

`wiki-012` is answerable only by joining two documents connected by a
`[[wikilink]]`. Expect both in `supplied`. If only the seed document appears,
graph expansion is not running and the retrieval arm is plain vector search
wearing a graph's name.

## Check 6 — score a set and read the report (User Story 3)

```bash
uv run bench run --question-set wiki-v1 --corpus wiki
uv run bench report <report_id>
```

Expect faithfulness and answer relevancy for both arms, context precision and
recall for `graph` only, `not_applicable` with a reason for `whole`, and `n`
beside every score. A score without `n` beside it is not finished.

## Check 7 — rebuild reproduces retrieval (SC-007)

```bash
uv run bench corpus rebuild wiki
uv run bench ask --question-id wiki-007 --strategy graph --show-supplied
```

Expect the same passages in the same order as before the rebuild. A difference
means something survived that was not derived from files, and the graph is no
longer disposable.

## Check 8 — the size curve (User Story 4)

```bash
uv run bench run --question-set worklog-v1 --corpus worklog --sizes 25,50,100,200,340
uv run bench report <report_id> --by-size
```

Expect the `whole` arm's `prompt_tokens` to grow with size while `graph` stays
roughly flat. That divergence is the finding; where the quality lines cross it
is the answer the subproject was built to give.

## Running the tests

```bash
uv run pytest                 # unit + contract. No network, no key, no Docker
uv run pytest -m integration  # needs Neo4j up
```

If `uv run pytest` ever requires a key or a network call, that is a defect: the
constitution puts evaluation outside CI, and a unit suite that reaches the
network drags it back in.
