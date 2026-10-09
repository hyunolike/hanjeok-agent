# Local validation and review

Run from the wiki root:

```sh
./harness/scripts/smoke.sh
scripts/build-index.sh --check
shellcheck scripts/build-bundle.sh harness/scripts/smoke.sh
python3 scripts/provenance.py check
scripts/build-bundle.sh hanjeok > /tmp/hanjeok-bundle.txt
python3 scripts/provenance.py metadata hanjeok > /tmp/hanjeok-bundle.meta.json
```

Compare both outputs to the agent's `server/src/main/resources/prompts/` files.
The complete bundle remains nine documents in declared order. The sidecar is not
inserted into the model's prompt or citation path set.

For a real new capture, preserve a new raw file and commit the captured bytes
before pinning its revision. Edit the canonical claim/source association, then
run `python3 scripts/provenance.py refresh`. Inspect the resulting diff: changed
claims must be needs-review. A refresh cannot turn a claim into reviewed.
A quote selector that no longer exists requires an explicit selector edit.
Only an actual human review may supply reviewer and an existing Git revision
whose document bytes match the reviewed hash. Missing experiment evidence in
choose-explanation-model remains unverified; do not synthesize outputs/approval.

The consumer adds response fields while retaining the existing citations array.
`generatedAt` is generation completion, `retrievedAt` is successful facts query
completion; neither is a forecast publication timestamp. Past targetDate values
remain past, and the five-minute explanation TTL cannot establish source freshness.
The fingerprint hashes the exact JSON bytes handed to the provider, so harmless
key-order changes can cause a safe extra cache miss.

Blocking responses check answer/question policy terms. Streaming checks question
policy topics before body output. Referential questions can follow earlier question
chains; prior answer text is never evidence. These finite topic checks can reject
an irrelevant citation but cannot prove every sentence or numeric claim.

A future remote integration must land the wiki generator/contract before the
consumer change, then synchronize body and sidecar together. CI uses full wiki
history to resolve content revisions; the agent refuses a mismatched sidecar.
This task performs local validation only. Do not run eval or demoReachability:
they can call real services; eval can incur LLM charges. Do not deploy the backend.
