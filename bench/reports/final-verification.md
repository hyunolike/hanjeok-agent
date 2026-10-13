# Final verification — wiki-only Retrieval Bench

Verified on 2026-10-13. The current scope is the existing wiki, whole/graph
comparison, stored question-set execution, NVIDIA-only answer/judge adapters,
request pacing, deadline accounting, sanitized diagnostics and body-free logs.
Personal-worklog loading and document-size evaluation were removed at the user's
request. Repeated hosted evaluation is excluded from completion.

## Clean checkout

A separate local clone at `/tmp/hermes-bench-clean-20261013` was created from
`799333baff05216192c96a40833bfc19afcf7e4a`, with no source modifications or copied
virtual environment. `uv sync --locked --python 3.13` installed all locked
dependencies into a new environment using Python 3.13.5. Offline installation
first failed because some locked wheels were absent from the cache; the normal
installation succeeded after downloading them. The source tree remained clean.

| Check | Actual result |
|---|---|
| Default offline suite | 125 passed, 27 integration tests deselected |
| Actual local Neo4j integration suite | 27 passed, 125 offline tests deselected |
| Ruff lint / format | Passed; 49 Python files formatted |
| `docker compose up -d --wait neo4j` | Existing container running and healthy |
| CLI wiki load and rebuild | Both succeeded; 14 docs / 57 chunks, revision `e7f4b44` |
| Real pinned local embeddings | 1024 dimensions, CPU; no hosted embedding calls |
| Retrieval after rebuilding | All ten supplied passages, metadata and scores identical |
| Whole strategy | Supplies all 57 stored chunks |
| HTTP corpus and saved-report reads | 200; saved report matches offline CLI output |
| Unsupported multi-size HTTP evaluation | 409 before model calls |
| Actual Uvicorn / curl | Local server started; corpus endpoint and OpenAPI returned 200 |
| Original wiki | Git status unchanged |
| Hosted calls during this verification | 0; API keys removed from the smoke process |

The isolated environment initially denied Bolt connections, Docker socket access
and local server binding. The same operations succeeded after the required
execution approvals. The temporary Uvicorn server was shut down after checking.
The pinned embedding revision and retrieval hash are in
[clean-checkout.json](clean-checkout.json).

Quickstart checks 1–5 use the offline answer/citation/pair contract tests plus
actual local retrieval; the clean checkout did not generate fresh NVIDIA answers.
Check 6 verifies saved-report reading and offline evaluation contracts. Check 7
uses actual wiki re-embedding and rebuilding. The hosted commands remain usable
as an optional flow, but repeating them is outside the requested completion.
The API key instruction was moved before server startup, and installation now
selects the Python version verified here.

## Preserved prior observations

The previously started process had already exited before the user's request to
exclude repeated evaluation could be applied. No further evaluation was started.
Its artifacts are preserved, with strict JSON, counts, question-file hash and
credential checks passing for all ten new files. Each report contains 60 arm
records, 30 pairs and 240 metric observations; JSONL scores match saved reports.

- [First report](690798ba-0251-4336-b79a-c55539d85e53.json): one unavailable-provider judge call.
- [Second report](5f0c9e39-1188-4625-918a-bbe435e2402c.json): 58 rate-limited judge calls.
- [Saved comparison](phase6-calibration.json): inconclusive; `comparable: false`, `passes: null`.

Both executions used NVIDIA with three-second process-wide pacing, the same
14-document generation and unchanged question set. Their loaded process predates
the later pacing-deadline and structured-log fixes, so these observations do not
validate those fixes; offline regression tests do. The original 0.05 tolerance
is unchanged and is not claimed as passed. No quality crossover is claimed.

## Existing application and build boundaries

No frontend, Kotlin application, build definition or CI file differs from the
base branch. Earlier checks on these unchanged files passed: Gradle build,
frontend typecheck, 87 frontend tests and `pnpm build --webpack`. An existing
React `act` warning appeared in the frontend tests. The default Turbopack build
failed with an environment port-binding denial even after execution approval;
its normal-environment CI result remains to be checked. No bundler setting was
changed to conceal that limitation.

## Review

One independent reviewer examined the full branch and found three Important
issues and no Critical issues. All three were reproduced with failing offline
tests and fixed in `88cb195`: first-use initialization now consumes the answer
deadline; local setup failures retain zero provider calls and a configuration
category; matching failed/missing execution samples cannot produce a full-set
comparison pass. Complete matching cohorts still compare normally.

After the one fix pass, both the implementation checkout and the separate clean
clone passed **130 offline tests and 27 actual Neo4j integration tests**. The clean
clone uses Python 3.13.5 and the locked dependencies; its source remained clean.
Ruff lint/format passed. No second review or hosted evaluation was run.
Three historical two-loader descriptions remain as deferred documentation
minors; there is no second production loader. Full review dispositions and
decision costs are in [final-review.md](final-review.md).

The branch is kept locally; no merge or push is part of this verification.
