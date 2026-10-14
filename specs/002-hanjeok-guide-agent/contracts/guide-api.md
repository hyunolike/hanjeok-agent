# Contract: Guide HTTP API

Serves User Stories 1 to 3. Read-only with respect to Hanjeok and the wiki
(FR-016). Base path `/guide`, beside the bench's `/bench/*`.

The frontend's `lib/guide.ts` is the only intended caller. Its fixtures under
`frontend/src/lib/guide-fixtures.ts` are recordings of the shapes below, and a
contract test on each side reads the same recorded stream.

## `POST /guide/ask`

Ask one question. Responds with `text/event-stream`.

**Request**

```json
{
  "question": "이번 토요일 경복궁 대신 조용한 곳 있어?",
  "visit_id": null,
  "strategy": "graph",
  "choice": null,
  "context": {"place_id": 653, "date": "2026-10-17"}
}
```

| Field | Rule |
| --- | --- |
| `question` | Required, 1–500 characters after trimming |
| `visit_id` | `null` on the first question. Afterwards the value the service issued. An unknown or expired id is treated as `null` and a new one is issued; it is not an error, because a visitor returning after a pause should not see a failure |
| `strategy` | Optional, `graph` or `vector`, default `graph`. The default exists because this is a visitor-facing endpoint; evaluation always states it |
| `choice` | Optional place id, sent when answering an `ask_user` outcome. Must be one of the candidates the service offered in this visit |
| `context` | Optional. What the calling screen already knows: `place_id` (integer) and `date` (`YYYY-MM-DD`), either or both, no other keys. Each fills only what the question leaves out — a place or date the question names wins. A screen's place wins over the previous question's in the visit. When the date came from the screen, a lookup for another day is refused, and the scope step says both came from the screen |

**Events**, in order. Exactly one of the last three ends every stream.

| Event | Data | When |
| --- | --- | --- |
| `visit` | `{"visit_id", "as_of": {"export", "wiki"}}` | First, always |
| `step` | A Step from the data model | Once per step, as it finishes. A step in progress is announced with `status: "running"` and the same `index`, then replaced |
| `answer` | `{"text", "citations": [{"id","kind","label"}], "partial"}` | Once, after verification. Never before |
| `path` | `{"nodes": [{"id","kind","label","region"}], "edges": [{"from","to","kind","rank"}]}` | Once, with or just after `answer` |
| `done` | `{"outcome": "answered", "model", "elapsed_ms", "generated_at"}` | Terminal |
| `ask_user` | `{"cause": "ambiguous_place", "prompt", "candidates": [{"place_id","name","region"}]}` | Terminal. No `answer` precedes it |
| `stopped` | `{"outcome", "cause", "message"}` | Terminal for `declined`, `no_grounds` and `failed` |

Rules:

- Answer text reaches the stream only inside `answer`, and only after every
  citation in it was found in the set of ids the steps produced (FR-004,
  FR-006).
- `message` in `stopped` is display-ready Korean and says what the visitor can
  do next. `cause` is from the fixed list in the data model (FR-031).
- A `step` with `status: "refused"` carries its `reason`. Refusals are visible
  to the visitor; they are part of how the answer was reached.
- If the connection drops before a terminal event, the client shows the steps
  it has and reports the stream as cut. It does not synthesise an answer.

**Non-stream responses**

| Status | Body | When |
| --- | --- | --- |
| 400 | `{"cause": "invalid_request", "detail"}` | Blank or over-long question, unknown strategy, `choice` not among offered candidates, `context` with another key or a malformed `place_id` or `date` |
| 429 | `{"cause": "usage_limit", "scope": "visitor"\|"day", "retry_after_s"}` | FR-030 |
| 503 | `{"cause": "not_ready", "detail"}` | No active generation, or the graph is unreachable |

## `GET /guide/places?query=…`

Name lookup for the path view when no question was asked (Story 2, scenario 3).

| Parameter | Rule |
| --- | --- |
| `query` | Required, 1–50 characters. Matched with spaces removed, exact first, then prefix, then substring |

**200**: `{"places": [{"place_id","name","region","has_congestion_data"}], "as_of"}`,
at most 10.

## `GET /guide/places/{place_id}`

A place and its neighbourhood (FR-023).

**200**

```json
{
  "place": {"place_id": 1234, "name": "경복궁", "region": "서울 종로구",
            "category": "…", "overview": "…", "has_congestion_data": true},
  "related": [{"place_id": 5678, "name": "…", "region": "…", "rank": 1}],
  "events": [{"id": "festival:…", "name": "…", "start_date": "…", "end_date": "…"}],
  "as_of": "2026-10-13T02:00:00Z"
}
```

`related` is in the service's rank order and is never re-sorted by the client.
No congestion value appears here: it is date-bound and is only ever fetched by
a question (FR-011).

**404**: `{"cause": "unknown_place"}`.

## `GET /guide/status`

**200**: `{"ready", "as_of": {"export","wiki"}, "counts": {"places","related","events","regions"}, "generation", "limits": {"per_visitor","per_day"}}`.
The refresh record of FR-021 and SC-009, readable without credentials.

## `GET /guide/eval/latest` and `GET /guide/eval/{report_id}`

The published evaluation report (FR-028), in the report shape of the data
model. `latest` returns 404 with `{"cause": "no_report"}` when none has been
published; the page then says so and does not show zeros.

## `GET /guide/eval/{report_id}/samples/{question_id}`

One evaluated question (Story 3, scenario 4): question, per strategy the
answer or its cause, steps, supplied passages, scores and forbidden-behaviour
findings.

## Not exposed

Refresh and evaluation are started from the command line
(`guide refresh --export <dir>`, `guide eval --question-set <file>`), not over
HTTP. A public endpoint that rebuilds the graph or spends model quota would
need authentication this demo does not have.

## Rules across all endpoints

- CORS allows GET and POST from the origins in `GUIDE_CORS_ALLOWED_ORIGINS`.
  No default origin in production; a missing value fails startup.
- Every response that contains service data carries `as_of`.
- No endpoint returns a stack trace or a provider message. Provider failures
  are logged with their category and surface as `model_failed`.
- Per-visitor limits key on `visit_id` and on the client address; the daily
  limit is process-wide. Both are in memory and reset on restart, which is
  stated on the status endpoint.
