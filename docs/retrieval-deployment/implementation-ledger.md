# Implementation ledger — retrieval deployment readiness

Base: aaed27772a48e19c465cab6b37717b6909c807d7 (Draft #13 diagrams/experiments, exact-head CI passed). Wiki Draft #32 final head 99b7d87723a0f7b64441404e85c20bdc9779bb59, smoke passed. Native execution approved; existing linked worktree reused with a separate local branch. No follow-up push.

Ruling: use a small ASGI application plus Uvicorn rather than a new web framework — body/read deadlines and admission are explicit, while the existing retrieval adapters remain reusable.
Ruling: production IAM validation belongs to private Cloud Run deployment; local test authentication is explicit loopback-only and does not prove IAM. Actual platform/IAM changes remain held.
Pre-flight: index API produces verified ID/hash/source metadata; Kotlin consumes the same pinned bundle/sidecar/model/index identity. Each request owns its citation validator and cache identity. Runtime index changes are manual immutable publication only.
