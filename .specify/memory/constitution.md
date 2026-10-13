# Retrieval Bench Constitution

This constitution governs `bench/`, the retrieval comparison subproject, and the
guide agent that grows out of it under `specs/002-hanjeok-guide-agent`, including
the screens that feature adds to `frontend/`. It does not govern `server/` or
`harness/`, which keep the practices they already have. Where this document and the repository README disagree about the
explanation service itself, the README wins.

## Core Principles

### I. Nothing Is Claimed That Was Not Measured

This subproject exists to answer one question with numbers: for a corpus of a
given size and shape, does graph-backed retrieval beat putting the whole corpus
in the prompt? A sentence like "GraphRAG answers better" may appear in this
repository only next to the run that produced it, the corpus it ran against, and
the question set it used. A result that favours the approach we spent more
effort on is still a result; a result with no run behind it is an opinion
wearing a number's clothes.

### II. The Two Strategies Share Everything But Retrieval

Same questions, same model, same prompt scaffold, same citation rules, same
judge. The only difference permitted between the full-injection arm and the
graph arm is **which passages reach the prompt**. Any other difference makes the
comparison measure that difference instead, and a benchmark that quietly
measures the wrong thing is worse than no benchmark, because it produces a
number people trust.

### III. Corpus Loaders Are Replaceable; The Pipeline Is Not

A corpus enters through a loader that emits documents, tags, links and evidence
edges. Everything downstream — graph build, retrieval, answering, scoring — sees
only that shape and never reads a corpus-specific field. The wiki
was the only corpus through feature 001. Feature 002 adds a second: public place
data exported from the Hanjeok service, per the user's 2026-10-13 direction. It
enters through the same seam as the wiki. A synthetic loader tests that seam
without depending on either. Findings apply to the corpus they were measured on
and are never carried from one corpus to another.

### IV. A Citation Is Checked Before It Is Shown

Every answer names the documents it used, and every named path is verified
against the corpus that was loaded. An answer citing a path that is not there is
discarded whole — not trimmed, not annotated. This rule is inherited from the
explanation service, and it is what makes retrieval quality measurable rather
than merely plausible: if invented citations were allowed through, faithfulness
scores would be measuring the judge's gullibility.

### V. Failures Are Loud, Especially Cheap Ones

A missing graph, an empty retrieval, a corpus that failed to load, an answer
that arrived with no citations — each ends the request with a named cause. No
silent fallback to the other arm, no empty-string answer recorded as a run, no
default corpus when the requested one is absent. A benchmark that degrades
quietly reports averages over runs that did not happen.

### VI. The Model Decides Nothing About Ranking

Which places are good alternatives, and in what order, is decided by the Hanjeok
backend. The agent may turn a question into lookups and explain what came back;
it may not select, score, add, drop or reorder places. This is inherited from the
explanation service, and widening what the agent can fetch does not widen what
it can decide. A lookup the model can call takes validated inputs from a fixed
set and returns a refusal reason when they are out of range; the model never
composes a query of its own.

## Constraints

- Python for this subproject. The explanation service stays Kotlin; nothing here
  changes it, and no code is ported from it.
- The graph store is disposable. Every node and edge is derived from files on
  disk, so the whole graph can be dropped and rebuilt from the corpus at any
  time. Nothing may live only in the database.
- Evaluation calls a real hosted model and consumes account quota, so it never
  runs in CI. Per the user's 2026-10-11 direction, hosted inference uses NVIDIA
  only and has no paid-provider fallback. Unit tests pass with no network or key.
- Corpus files are read-only to this subproject. It never writes to the wiki or
  to the Hanjeok service. Per the user's 2026-10-13 scope correction, personal
  worklogs are not loaded.
- Hanjeok data arrives only as a file exported on the Hanjeok side. Nothing here
  holds credentials to the Hanjeok database. Only public tourism data is taken;
  member accounts, feedback, photos and view history never enter a corpus.
- Date-bound facts, such as a congestion forecast, are fetched from the Hanjeok
  service when asked and are never served from a copy.
- Measured numbers are committed as run artifacts with the corpus revision they
  ran against. A number without its corpus revision cannot be reproduced and is
  therefore not evidence.

## Development Workflow

- Specification precedes implementation: `spec.md` states what and why with no
  technology named, `plan.md` chooses the technology, `tasks.md` orders the
  work, and code follows.
- A task that changes what is measured, or how, amends `spec.md` in the same
  change. Discovering mid-implementation that the measurement was wrong is
  expected; leaving the specification describing the old measurement is not.
- Each arm of the comparison is runnable alone. If one cannot be demonstrated
  without the other, they are coupled somewhere they should not be.

## Governance

This constitution outranks convenience, including the convenience of the person
who wrote it. When a principle blocks a shortcut, the shortcut is what gives
way, or the principle is amended in its own commit that says why — never
silently bent inside a change that is nominally about something else.

Principle II is the one most likely to be violated by accident, because most
accidental violations look like improvements to one arm. Any change touching
prompt text, model settings or the question set states in its commit message
which arms it affects; if the answer is "one", it needs a reason.

**Version**: 1.1.0 | **Ratified**: 2026-09-29 | **Last Amended**: 2026-10-13
