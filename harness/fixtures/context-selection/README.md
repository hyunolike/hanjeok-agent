# Fixture contract

Synthetic questions/history and the existing synthetic course fixture only. Each case declares relevant evidence paths before running the selector. The set is a coverage oracle for this test suite, not independent proof of answer semantics. All eight policy documents remain mandatory regardless of a case's narrower relevant paths.

Selection never reads scripted answers, expectedDecision or requiredEvidencePaths. It reads only the question, user questions in history, and authoritative backend place names/visit positions. Poisoned history answers must not affect selection. References are resolved conservatively; unsupported topics, unknown intent, empty questions, override attempts, unresolved/ambiguous references use the verified full bundle.

Answers and tool requests are scripted. Successful, failed and rejected tool paths execute the production AgentLoop with no network runner. The omitted-seed cases intentionally differ between FULL (path present) and SELECTED (path absent). The unrelated-valid-citation case fails both arms because the current bounded congestion-topic validator requires the congestion policy; it does not establish general semantic entailment.

The suite pins the body and sidecar SHA-256. Refreshing either requires explicit fixture review and a new baseline. Omit no policy to inflate byte savings. Report original source bytes separately from serialized system bytes (markers and separators also cost bytes). Actual tokens, billing, model quality, accuracy and latency are unmeasured.
