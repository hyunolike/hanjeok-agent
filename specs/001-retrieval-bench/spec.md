# Feature Specification: Retrieval Bench

**Feature Branch**: `001-retrieval-bench`

**Created**: 2026-09-29

**Status**: Draft

**Execution profile (Phase 3)**: The retrieval implementation uses exact cosine
ranking inside the requested corpus, followed by bounded one-hop expansion.
Future measurements must identify this profile; its latency does not measure
approximate nearest-neighbour index performance. Citation validation checks
both corpus membership and membership in the passages actually supplied.

**Execution profile (Phase 4)**: Both strategies share a configurable conservative
input byte budget, checked before initial and repair calls. Oversize inputs fail
without truncation. Run artifacts capture first-request inputs and provider call
counts so selected-but-unsent context is distinguishable. Pair validity also
checks load generation, size, question text, model settings and common inputs;
unknown metadata or mismatch excludes the pair. A failed arm is recorded and
prevents scoring eligibility without preventing execution of the other arm.

**Input**: Answer, with measurements rather than assertion, whether retrieving
passages from a linked corpus beats putting the whole corpus in the prompt — and
report the quality and cost observed on the existing wiki.

## Why This Exists

This repository already answers questions about a curated wiki by putting the
entire wiki into every prompt. That was a deliberate choice and the README
argues for it, but the argument rests on an untested claim: that the corpus is
small enough for retrieval to be unnecessary. "Small enough" has never been
given a number, and nobody here has built the alternative to compare against.

So the claim is currently unfalsifiable, which is the one property this
repository elsewhere refuses to tolerate. Every other assertion it makes —
violation rates, blocked citations, bundle size — is attached to a run. This one
is attached to an intuition.

The work is to build the alternative, run both against the same questions, and
publish their measured quality and cost on the wiki. Corpus growth and a
crossover claim are outside the current scope. The honest expectation is that retrieval loses on today's corpus. That
is a finding, not a failure, and it is only worth anything if the run that
produced it exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask one corpus a question and see where the answer came from (Priority: P1)

Someone submits a question about a curated corpus and receives an answer that
names the documents it drew on. They can open each named document and read the
passage the answer used. If the system could not ground an answer, it says so
and shows nothing rather than answering from general knowledge.

**Why this priority**: Without a working answer path there is nothing to
compare. This is also the smallest slice that is worth showing to another
person, and it is the slice that proves the citation rule works before any
measurement depends on it.

**Independent Test**: Load one corpus, ask ten questions whose answers are known
to be in it, and confirm every answer names only documents that exist and that
the named passages actually support the claims.

**Acceptance Scenarios**:

1. **Given** a loaded corpus, **When** a question is asked whose answer appears
   in one document, **Then** the answer names that document and the passage it
   used.
2. **Given** a loaded corpus, **When** a question is asked whose answer requires
   joining two documents connected by a link, **Then** the answer names both.
3. **Given** a loaded corpus, **When** a question is asked that the corpus does
   not cover, **Then** the system reports that it has no grounds and returns no
   answer text.
4. **Given** an answer naming a document path absent from the loaded corpus,
   **When** the answer is assembled, **Then** the whole answer is discarded and
   the request ends with an explicit cause.

---

### User Story 2 - Ask the same question both ways and compare (Priority: P1)

The same question is put to both strategies — whole-corpus prompting and
retrieval — under identical conditions, and the two answers are shown side by
side with what each one was given as context and what it cost.

**Why this priority**: This is the point of the subproject. It shares P1 with
Story 1 because an answer path that cannot be compared answers no question worth
asking here.

**Independent Test**: Run a single question through both arms and confirm the
only recorded difference in their inputs is the set of passages supplied.

**Acceptance Scenarios**:

1. **Given** one question and one corpus, **When** both arms run, **Then** both
   receive the same question text, the same instructions and the same model
   settings, and differ only in supplied passages.
2. **Given** a completed pair of runs, **When** the result is inspected, **Then**
   it records for each arm the passages supplied, the answer, the cited paths,
   the token counts and the wall-clock time.
3. **Given** one arm fails, **When** the pair is recorded, **Then** the other
   arm's result is still recorded and the failure is stored with its cause
   rather than omitted.

---

### User Story 3 - Score a question set and get a number per strategy (Priority: P2)

A prepared set of questions runs through both arms unattended and produces a
report: per-strategy scores for whether answers are supported by their cited
passages, whether they address the question, and — for the retrieval arm —
whether the passages it fetched were the ones needed.

**Why this priority**: Turns anecdote into evidence. It depends on Stories 1 and
2 and is worthless before them, but without it the comparison is two answers a
person eyeballed.

**Independent Test**: Run the set twice against an unchanged corpus and confirm
the scores move less than a stated tolerance.

**Acceptance Scenarios**:

1. **Given** a question set and a loaded corpus, **When** the scoring run
   completes, **Then** a report gives each strategy a score per metric and the
   count of questions each metric could be computed for.
2. **Given** a metric that requires retrieved passages, **When** it is applied to
   the whole-corpus arm, **Then** the report marks it not applicable rather than
   recording a zero.
3. **Given** a completed run, **When** the report is stored, **Then** it records
   the corpus revision, question set revision, model identity and timestamp.

---

### User Story 4 — Withdrawn from current scope

The user excluded personal-worklog loading on 2026-10-13. Document-size sampling
and crossover measurement are consequently outside the current scope. Reports
compare the two strategies on the existing full wiki and make no crossover claim.

### Edge Cases

- A corpus document names a source file that does not exist: the document loads,
  the missing edge is reported at load time, and the load does not fail.
- Two documents contradict each other and both are retrieved: both reach the
  answer step with their conflict markers intact; resolving the conflict is not
  this system's job, but hiding it is forbidden.
- Retrieval returns nothing above threshold: the request ends with "no grounds"
  rather than falling back to supplying the whole corpus, which would silently
  convert one arm into the other.
- A question set entry has no answer anywhere in the corpus: both arms should
  decline, and declining counts as correct for that entry.
- The corpus changes between the two arms of a pair: the pair is invalid and is
  recorded as such rather than scored.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load a corpus from files on disk into a form that
  records, for each document, its identity, its type, its tags, its links to
  other documents and its cited evidence files.
- **FR-002**: System MUST select the wiki corpus per request and isolate its
  graph state. The generic loader seam remains, but no additional production
  corpus loader is in the current scope.
- **FR-003**: System MUST answer a question using only passages supplied to it
  from the selected corpus.
- **FR-004**: System MUST make every answer name the document paths it used.
- **FR-005**: System MUST verify each named path against the loaded corpus and
  discard the entire answer if any path is absent.
- **FR-006**: System MUST offer two strategies for choosing supplied passages:
  supplying the whole corpus, and selecting passages by relevance and then
  widening the selection along document links and shared evidence.
- **FR-007**: System MUST hold every input other than supplied passages
  identical between the two strategies for a given question.
- **FR-008**: System MUST record, per run, the supplied passages, the answer,
  the cited paths, token counts, elapsed time and the outcome cause.
- **FR-009**: System MUST run a stored question set through both strategies
  without supervision and produce one report.
- **FR-010**: System MUST score answers for support by cited passages and for
  addressing the question, and score the retrieval strategy for whether it
  fetched the needed passages.
  Support is judged using only actually supplied passages belonging to cited
  documents, including their attributes. The same restriction applies to both
  arms. Declines have no numeric answer score. Outcome counts retain every
  request; unsupported-question correctness uses all requested unsupported
  questions, including failures, as its denominator.
- **FR-011**: System MUST mark a metric not applicable rather than scoring zero
  when a strategy cannot produce the input that metric needs.
- **FR-012**: System MUST stamp every report with corpus revision, question set
  revision, model identity and timestamp.
  Loaded generation, size, common inputs and model settings must match the
  frozen evaluation profile. Incompatible or failed pairs remain recorded but
  are excluded from scoring. Every metric reports successful sample count,
  skipped samples and judge failures alongside its mean and split by kind.
- **FR-013**: System MUST end a failed request with a named cause drawn from a
  fixed set, and never with an empty answer presented as an answer.
- **FR-014**: System MUST rebuild its entire derived state from the corpus files
  on demand, holding nothing that cannot be regenerated.
- **FR-015**: System MUST NOT write to any corpus.
- **FR-016**: Users MUST be able to run either strategy alone.
- **FR-017**: System MUST expose the answer path over an interface a person can
  call without reading the source.

### Key Entities

- **Corpus**: a named, versioned set of documents on disk, with a size and a
  link density. The wiki is in scope; the generic interface permits future loaders
  only when separately requested.
- **Document**: one unit a citation can name. Has a path, a title, a type, tags,
  links to other documents, cited evidence files, and prose. May carry recorded
  conflicts with other material.
- **Evidence File**: raw material a document cites. Not itself citable in an
  answer; its role is to connect documents that drew on the same material.
- **Passage**: the unit supplied to the answering step and the unit a score can
  point at. Belongs to exactly one document.
- **Strategy**: a way of choosing which passages are supplied. Exactly two at
  the outset.
- **Run**: one question answered by one strategy against one corpus revision,
  with its inputs, output, cost and outcome.
- **Question Set**: a stored list of questions, each with what a correct answer
  must contain and which documents ought to support it.
- **Report**: the scores for one question set across strategies, stamped with
  what produced it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a question whose answer lies in one document, both strategies
  cite that document in at least 9 of 10 runs.
- **SC-002**: Across the question set, no answer that reaches a reader cites a
  path absent from the corpus — zero tolerance, counted per run.
- **SC-003**: For a question that requires joining two linked documents, the
  retrieval strategy supplies both in at least 8 of 10 runs, and this is
  measured separately from single-document questions.
- **SC-004**: Re-running an unchanged question set against an unchanged corpus
  moves each reported score by less than 0.05, when model/scoring profiles and
  successfully scored question membership match and neither report contains
  judge failures. Missing or unequal samples are inconclusive, never a pass.
  The 2026-10-11 NVIDIA calibration completed both sets, but the second had
  12 failed arm calls, nine excluded pairs and 44 failed judge observations.
  Its matched partial single-document cohorts moved at most 0.0096484774;
  no multi-document repeat scores survived. The full-set tolerance remains
  unverified; this observation does not justify changing 0.05. See the
  [execution evidence](../../bench/reports/phase5-evaluation.md).
- **SC-005**: Withdrawn with document-size sampling on 2026-10-13. Existing
  single-corpus runs still record provider token usage, elapsed time and outcomes;
  no crossover is asserted.
- **SC-006**: A person who has not seen the code can run one question through
  both strategies and read both answers with their sources, following only the
  written instructions.
- **SC-007**: Dropping all derived state and rebuilding from corpus files
  reproduces the same retrieval results for the same question.

## Assumptions

- The curated wiki this repository already consumes is the only corpus in scope.
  It has typed, linked documents with recorded evidence. Findings apply to that
  corpus and do not establish behavior at larger document counts.
- Recorded conflicts between documents are prose, not references, in at least
  one corpus. They are carried as document attributes and supplied alongside the
  document, not turned into links, because parsing prose into structure would
  break whenever the prose is reworded.
- A question set does not exist yet and must be written as part of this work.
  Roughly thirty questions, mixed between single-document, multi-document and
  unanswerable, is the initial target.
- Scoring uses a model as judge and therefore costs money and varies between
  runs. SC-004 fixes the tolerance this is allowed to consume.
- The existing explanation service is not modified. Whole-corpus prompting is
  reimplemented in this subproject so both arms share one prompt path, as the
  constitution requires; comparing against the existing service directly would
  vary language, framework and prompt at once.
- No personal worklogs are loaded, and no additional corpus or synthetic growth
  is introduced to replace them.

## Out of Scope

- Changing the explanation service, its prompt, or its deployment.
- Writing to either corpus, including corrections found while reading them.
- A user interface. The answer path is callable; looking at results is a
  developer's task here.
- Choosing a production retrieval strategy. This subproject reports; it does not
  migrate anything.
