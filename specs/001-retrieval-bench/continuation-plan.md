# Retrieval Bench remaining work

> Execute inline with superpowers:executing-plans. Existing approved spec,
> plan and T044–T054 are the authority; this file resolves their interfaces.

Goal: finish NVIDIA calibration, the worklog size curve and clean-checkout checks.
Baseline: `24c038a`, locked `feat/graphrag-bench` worktree.

## Constraints

- NVIDIA only, no fallback or automatic retries; identical answer policy per arm.
- Corpus read-only, no document duplication, no truncating whole context.
- Only `LoadedDoc` crosses the loader seam; attrs are opaque downstream.
- Commit observations with failures and denominators; never claim unmeasured quality.
- No merge, push or deployment is included.

## Task order and interfaces

1. Calibration transport: `provider.py` owns a process-wide request-start pacer
   and whitelisted diagnostics. Models propagate status/category without provider
   bodies or headers. Pipeline/runner persist diagnostics; judge records call
   errors. Tests use real SDK mock transport returning 429 with secret text and
   verify stored evidence is sanitized. Fake-clock pacing tests prove spacing.
   Run the wiki set twice under the same profile while implementing the curve.
2. T044–T047: `WorklogLoader(root, seed=20261012)` reads only `projects/**/*.md`,
   retains project/type/tech/status, resolves sparse links, reports malformed or
   credential-shaped documents. `plan_samples(sizes, required_paths)` loads once,
   produces immutable snapshots, nested anchored samples and content-hashed
   manifests. Reject missing anchors, duplicate/invalid sizes, unavailable sizes,
   symlinks outside root. Tests prove no corpus writes, links stay in sample,
   discarded status reaches the answer prompt, nested sampling and hash drift.
3. T048–T049: runtime exposes generic optional loader sampling and rebuild from
   validated LoadResult. `eval/curve.py` orchestrates full-corpus child evaluations
   inside one runtime evaluation lock, after validating every snapshot/reference.
   Parent report persists progress and child IDs, manifests and by-size summaries.
   Failure retains completed children and stops further calls if storage fails.
   CLI accepts `run --sizes` and offline `report --by-size`; HTTP uses existing
   sizes contract. Tests cover smallest-size references, queued jobs, partial
   failures, budget failures and offline reports without a runtime.
4. T052: each persisted arm emits a JSON log with IDs, size, retrieval/expansion
   counts, repairs, outcome, call count and sanitized diagnostic; no answer,
   question, body or secret. Logs go to stderr, preserving CLI JSON stdout.
5. T050: actual local Neo4j/NVIDIA curve at 25/50/100/200/340, same questions,
   model, retrieval, pacing and fixed shared byte budget. Report actual provider
   prompt usage separately from exact supplied UTF-8 bytes. Unsents have unknown
   token usage, never an invented zero-cost success. No price/quality winner
   inferred from capacity failures or unmatched samples.
6. T053–T054: test clean-checkout setup/CLI/HTTP using documented environment,
   run default/integration tests and Ruff, run existing Gradle/frontend checks,
   confirm build inputs and CI unchanged. Document environment/provider failures.
7. One independent final review per executing-plans, one RED→GREEN fix pass,
   final verification, commit evidence and findings, remove only own scratch ledger.

## Review focus

- Sample preflight failure must not erase the loaded corpus or invoke models.
- Concurrent rebuilds must not mix sizes or mutate a prepared sample identity.
- Candidate symlinks, malformed YAML and credential-shaped text must not escape
  the read-only boundary or enter model requests/artifacts.
- Provider exceptions/retry headers must not leak bodies, secrets or fabricate usage.
- A failed large whole arm must stay a failure; graph-only success is not a
  paired quality result and cannot establish a quality crossing point.

Verification gates for each code task: targeted test fails first, passes after
implementation, then full offline suite. Final gate adds real Neo4j integration,
lint/format, actual observations, existing application builds and artifact audit.
