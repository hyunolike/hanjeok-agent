# Remaining implementation plan: Retrieval Bench

Updated 2026-10-13 after the user explicitly excluded personal-worklog loading.
The previous document-size evaluation plan is withdrawn; it must not be resumed.
No alternative corpus or synthetic document growth is authorized.

Retain the existing wiki loader, whole/graph pair evaluation, NVIDIA-only answer
and judge adapters, process-wide request pacing, deadline accounting, sanitized
provider diagnostics and body-free per-run logging.

Remaining work:

1. Repeated NVIDIA evaluation is excluded by the user's latest instruction.
   Preserve already-written artifacts, run no further hosted evaluation, and
   make no claim that the original 0.05 repeatability criterion has passed.
2. Verify the wiki quickstart from a clean checkout (T053).
3. Keep the existing service, frontend, build and CI definitions unchanged.
   Gradle and frontend tests passed; Webpack build passed. The default Turbopack
   build encountered an environment port-binding denial and remains unverified
   in this environment.
4. Review the remaining changes and evidence before preparing a pull request.

Removal verification: no personal-worklog loader, dedicated question set,
sampling dispatch or size-report CLI remains; the existing offline suite and
actual local Neo4j integration tests must pass.
