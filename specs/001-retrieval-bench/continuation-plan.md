# Remaining implementation plan: Retrieval Bench

Updated 2026-10-13 after the user explicitly excluded personal-worklog loading.
The previous document-size evaluation plan is withdrawn; it must not be resumed.
No alternative corpus or synthetic document growth is authorized.

Retain the existing wiki loader, whole/graph pair evaluation, NVIDIA-only answer
and judge adapters, process-wide request pacing, deadline accounting, sanitized
provider diagnostics and body-free per-run logging.

Completion status (2026-10-13): all in-scope implementation and verification
steps below are complete. See [final verification](../../bench/reports/final-verification.md).

1. Repeated NVIDIA evaluation is excluded by the user's latest instruction.
   Preserve already-written artifacts, run no further hosted evaluation, and
   make no claim that the original 0.05 repeatability criterion has passed.
2. Verified the wiki quickstart from a clean checkout (T053), then verified the
   final review fixes there: 130 offline and 27 actual integration tests passed.
3. Keep the existing service, frontend, build and CI definitions unchanged.
   Gradle and frontend tests passed; Webpack build passed. The default Turbopack
   build encountered an environment port-binding denial and remains unverified
   in this environment.
4. Completed one independent full-branch review and one verified fix pass for
   its three Important findings. Three historical documentation minors are
   deferred and listed in the report. The branch is ready for a pull request;
   no push or merge is authorized by this plan.

Removal verification: no personal-worklog loader, dedicated question set,
sampling dispatch or size-report CLI remains; the existing offline suite and
actual local Neo4j integration tests must pass.
