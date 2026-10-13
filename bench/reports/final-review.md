# Final independent review and decisions

Reviewed the full branch from `f7a917f` to `2c4180b`, plus the scope-document
corrections. The reviewer used a fresh context and read-only tools. No hosted
calls or database mutations were made during review.

## Findings and disposition

No Critical issues. Three Important issues were fixed in one pass (`88cb195`):

1. First-use lazy initialization could consume the deadline and still start SDK
   inference. The new initialization-deadline test observed an SDK start after
   two seconds under a one-second limit before the fix, then zero SDK calls.
2. Matching excluded pairs/missing observations could pass repeatability using a
   surviving subset. Three failing coverage cases now stay inconclusive, while
   complete matching reports still compare normally.
3. Missing credentials were counted as one provider attempt. The new test now
   observes zero transport construction/calls and a sanitized `configuration`
   category, while real failed transport attempts still count.

All five regression cases were observed failing before implementation and passed
following the fixes. Both the working checkout and the clean clone then passed
130 offline and 27 actual Neo4j integration tests; lint and formatting passed.
No rereview or additional hosted evaluation was needed.

## Deferred minors

Historical two-loader wording remains in the research endnote, task T016 and the
frontmatter module docstring. These are documentation only; the production
runtime registers only the wiki loader. They do not authorize another corpus.

## Rulings I made

The following is the complete ordered decision record for this continuation.
Items 2, 3, 7 and 8 describe the withdrawn worklog/sampling implementation, which
was removed before completion. They are retained as history, not current scope.
The final fourteen entries dispose of every behavior the reviewer declined to
judge. Each entry preserves the consequence or limitation of that decision.

1. Ruling: Continue approved architecture inline; supplemental plan resolves interfaces without new approval — existing user scope — cost: larger final review range.
2. Ruling: Inventory has 350 candidate markdown files; malformed 3 and credential-shaped 4 will be reported/excluded before hosted calls — actual observed input hazard — cost: safe population343 differs from older documented283/340 total.
3. Ruling: Anchor all reference docs, seeded stable nested remainder, hash raw selected content/manifest — questions remain answerable at smallest size — cost: measures distractor growth rather than unbiased population sampling.
4. Ruling: Add process-wide pacing and sanitized status observations, retain no automatic retries — prior failures lacked diagnosable status — cost: longer measurements and external availability still not guaranteed.
5. Ruling: Token counts remain actual provider prompt usage, exact supplied bytes are separate — no tokenizer approximation presented as actual tokens — cost: unsent oversize prompts have no provider token measurement.
6. Ruling: Calibration outcome gates quality-crossing claims, not implementation of measurement — an inconclusive experiment is reportable — cost: no claimed strategy winner if samples remain incompatible.
7. Ruling: Fixed1,000,000-byte example for the worklog curve, same both arms/all sizes —25/50 expected fit,100+ explicitcapacity failure — cost: capacity boundary reflects configured budget, not discovered model context limit.
8. Ruling: SC005 uses actual provider prompt tokens with measured n/unknown attempts plus exact selected-contextbytes — no invented supplied-only tokenizer count — cost: provider token count includes the common instructions/schema.
9. Ruling: Keep existing frontend bundler/configuration and verify via supported --webpack alternate — Turbopack binding denied even after escalation — cost: default Turbopack build is unverified in this environment and must run in normal CI.
10. Ruling: User scope correction supersedes the previous growth plan — direct user instruction — cost: crossover claims cannot be measured in the current scope.
11. Ruling: Exclude repeated hosted evaluation from completion and preserve existing observations — explicit user direction — cost: SC004 remains unverified.
12. Ruling: T053 verifies clean installation, real local retrieval and offline answer/evaluation transport contracts without additional hosted calls — excludes repeated evaluation and avoids quota failures — cost: hosted flow is evidenced by existing artifacts, not a new clean-checkout NVIDIA run.
13. Ruling: Test canonical wiki e7f4b44 rather than another worktree a110bf5 — existing benchmark question provenance — cost: verification covers the pinned snapshot, not all newer wiki edits.
14. Ruling: Keep default Turbopack limitation recorded and use unchanged-build prior evidence rather than rerunning unrelated builds — no app/CI changes since those checks — cost: normal-environment default frontend build must still run in CI.
15. Ruling: Preserve completed observations even though repeats are no longer required — measurement provenance must not be erased — cost: two extra reports increase branch size and their failed judgments cannot establish repeatability.
16. Final: Ruling: No further hosted repetition/SC004 attainment — explicit user exclusion — cost: repeatability remains unverified.
17. Final: Ruling: No personal-worklog/replacement corpus/growth — explicit user exclusion — cost: no crossover conclusion.
18. Final: Ruling: Preserve archived scores without fresh semantic validation — historical observations, not current-fix proof — cost: limited quality evidence.
19. Final: Ruling: No claim of deterministic NVIDIA quality or independent same-model judging — empirical limits — cost: judge bias and variance remain.
20. Final: Ruling: Retain exact cosine rather than ANN/throughput optimization — documented wiki profile — cost: large-corpus throughput unknown.
21. Final: Ruling: Retain summaries and512-token embedding window — existing measured strategy — cost: long-section retrieval misses remain possible.
22. Final: Ruling: Citation gate checks identity/membership, semantic faithfulness is measured afterward — current design — cost: valid paths do not guarantee factual entailment.
23. Final: Ruling: Keep local job ownership/no auto-resume or cancellation API/immediate shutdown — documented local scope — cost: manual recovery and bounded waits.
24. Final: Ruling: No distributed rebuild-lock guarantee — only snapshots/local locks verified — cost: concurrent server processes must not coordinate rebuilds implicitly.
25. Final: Ruling: Retain atomic reports/flushed JSONL without power-loss durability promise — existing durability scope — cost: machine failure can lose recent observations.
26. Final: Ruling: Calibration is limited to unchanged loaded implementation — no cross-version equivalence proof — cost: different code versions cannot establish repeatability from metadata alone.
27. Final: Ruling: No additional untrusted-corpus/path or Markdown hardening — pinned wiki only — cost: no guarantee for arbitrary untrusted repositories/dialects.
28. Final: Ruling: Keep prior unchanged-app checks/defaultTurbopack limitation — no app/build changes — cost: default normal-environment frontend build remains a CI check.
29. Final: Ruling: Generated Spec Kit commands are tooling inventory, not exercised benchmark runtime — current verification scope — cost: those commands are not integration-verified here.
