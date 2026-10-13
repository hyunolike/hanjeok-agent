# Quickstart: Hanjeok Guide Agent

How to see each user story working. Commands are run from the repository root
unless a directory is given. Contracts are in [contracts/](contracts/); shapes
are in [data-model.md](data-model.md).

## Screens only, no service

Needs Node 22 and pnpm.

```bash
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:3000/ko/ask` with `NEXT_PUBLIC_GUIDE_BASE_URL` unset.
The page says it is replaying a recording. Expected:

- An example question plays its steps in order, then the answer with record
  and policy chips of two different kinds.
- `/ko/ask?demo=ambiguous`, `?demo=no-data`, `?demo=declined`, `?demo=failed`,
  `?demo=partial` and `?demo=limit` each show the state of that name from
  `contracts/screens.md`.
- "Show path" opens the path of that answer under it, places in rank order.
- `/ko/eval` shows the fixture report; `/ko/design` shows the design values,
  components and six poses in both appearances.

```bash
pnpm typecheck && pnpm test && pnpm build
```

All three pass with no backend running.

## Service on the synthetic export

Needs Python 3.13, uv and Docker.

```bash
cd bench
docker compose up -d
uv sync
uv run guide refresh --export tests/fixtures/hanjeok-export
uv run bench corpus load wiki
uv run pytest
uv run pytest -m integration
```

Expected: `guide refresh` prints the counts it took in and a generation id.
Unit and contract tests pass with no network and no key. Integration tests
pass against local Neo4j with fake models.

```bash
GUIDE_LIVE_MODE=replay uv run uvicorn guide.api:app --port 8090
curl -s localhost:8090/guide/status
curl -sN localhost:8090/guide/ask -H 'content-type: application/json' \
  -d '{"question":"이번 토요일 가람궁 대신 조용한 곳 있어?"}'
```

Expected: `status` reports `ready: true` with counts. The stream carries
`visit`, several `step` events, `answer`, `path`, `done`, in that order.
`GUIDE_LIVE_MODE=replay` serves the two Hanjeok endpoints from recorded
responses, so no call leaves the machine. Answering needs `NVIDIA_API_KEY`;
without it the stream ends with `stopped` and cause `model_failed`.

Point the frontend at it:

```bash
cd frontend
NEXT_PUBLIC_GUIDE_BASE_URL=http://localhost:8090 pnpm dev
```

The same screens now show live steps, and the replay notice is gone.

## Failed refresh keeps the previous copy (Story 4)

```bash
uv run guide refresh --export tests/fixtures/hanjeok-export-broken
curl -s localhost:8090/guide/status
```

Expected: the refresh exits non-zero naming the mismatched file, and `status`
still reports the earlier generation and counts.

## Evaluation (Story 3)

Costs model quota. Never run in CI.

```bash
uv run guide eval --question-set questions/hanjeok-v1.yaml --record-live
uv run guide publish --report <report_id>
```

Expected: a report under `bench/reports/` with both strategies, every metric
with its sample count, forbidden-behaviour counts, the export hash and the
recording time. `/ko/eval` then shows that report.

On the synthetic export this checks the machinery only. Published numbers come
from a real export, which is produced on the Hanjeok side
([contracts/hanjeok-export.md](contracts/hanjeok-export.md)).

## Deployed demo

After the deployment tasks: the Space address answers `GET /guide/status`
with `ready: true`, and the Vercel site's `/ko/ask` shows no replay notice.
