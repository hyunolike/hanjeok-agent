# Contract: HTTP API

Serves FR-016 (either strategy runnable alone) and FR-017 (callable without
reading the source). Read-only with respect to every corpus (FR-015).

Base path `/bench`, chosen so nothing collides with the explanation service's
`/agent/*` should the two ever sit behind one host.

## `POST /bench/ask`

Answer one question with one strategy. This is the whole of User Story 1 and
half of User Story 2.

**Request**

```json
{
  "question": "왜 LLM이 순위를 정하지 않는가?",
  "corpus": "wiki",
  "strategy": "graph"
}
```

| Field | Rule |
|---|---|
| `question` | Required, 1–2000 characters. Bounded because an unbounded prompt is a cost amplifier on an endpoint that calls a paid model |
| `corpus` | Required. A loaded corpus name. **No default** — a default silently answers from the wrong corpus and the answer still looks right |
| `strategy` | Required, `whole` or `graph`. No default, same reason |

**200 — answered**

```json
{
  "outcome": "answered",
  "answer": "…",
  "citations": ["concepts/alternative-scoring.md"],
  "supplied": [
    {"doc": "concepts/alternative-scoring.md", "chunk": "…#scoring", "chars": 812}
  ],
  "usage": {"prompt_tokens": 4120, "completion_tokens": 190, "elapsed_ms": 2310},
  "corpus_revision": "a1b2c3d"
}
```

`supplied` is in the response, not just the log, because User Story 2 requires a
person to see what each arm was given. Without it the two answers are
uncomparable by eye, and the endpoint's whole purpose is that comparison.

**200 — declined**

```json
{
  "outcome": "no_grounds",
  "answer": null,
  "citations": [],
  "supplied": [],
  "usage": {…},
  "corpus_revision": "a1b2c3d"
}
```

Declining is a normal outcome, not an error, so it carries 200. `answer` is
`null`, never `""` — an empty string is the shape of a successful answer and
would be recorded as one downstream.

**422 — invalid citations**

```json
{"outcome": "invalid_citations", "cause": "cited path not in corpus: made/up.md"}
```

The whole answer is discarded (FR-005). The body never contains the discarded
text: shipping it invites a caller to display "the answer we rejected", which is
precisely the failure the rule prevents.

**409 — corpus not loaded** · **503 — model or graph unreachable**

Distinct because one is the caller's mistake and the other is the operator's. A
single 500 for both sends the reader to the wrong place.

## `POST /bench/run`

Run a stored question set through both strategies and produce one report
(User Stories 3 and 4).

**Request**

```json
{"question_set": "wiki-v1", "corpus": "wiki", "sizes": [17]}
```

`sizes` selects the sampled corpus sizes to run; a single-element list is one
point on the curve. Absent, it means the corpus at full size.

**202 Accepted**, returning `{"report_id": "…", "status_url": "/bench/reports/…"}`.
Accepted rather than 200 because a 30-question set across two arms is minutes of
model calls, and holding a socket open for it makes the timeout the limit on
question-set size.

## `GET /bench/reports/{id}`

The report of the data model, or `{"status": "running", "completed": 12, "total": 60}`.

## `GET /bench/corpora`

What is loaded, so a caller can discover valid `corpus` values rather than
guessing.

```json
[{"name": "wiki", "revision": "a1b2c3d", "docs": 17, "chunks": 94, "loaded_at": "…"}]
```

## `POST /bench/corpora/{name}/rebuild`

Drop and rebuild derived state from files (FR-014, SC-007). Returns counts and
the list of unresolved links and sources dropped during load — the load succeeds
with them, and this is where they are visible.

## Rules across all endpoints

- Never write to a corpus.
- Every response carrying an answer or a score also carries `corpus_revision`.
- Every failure names a cause from the data model's fixed `outcome` set.
- Bodies never echo an API key, a filesystem path outside the corpus, or model
  error text verbatim.
