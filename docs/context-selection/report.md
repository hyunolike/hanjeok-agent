# FULL vs SELECTED_EXPERIMENT — offline comparison

Production remains **FULL**. Baselines: agent `ea47917fd6e031b0f2c6ae387249dabd690d2aed`, wiki `7fc19c0c4a034868866bcf5a920e3f82050830c7`. This is a scripted wiring evaluation with **zero paid-model or remote backend calls**. The selector and scripted ports are in the harness source set, outside the server image. Existing production prompt, packaged resources, singleton wiring and cache code remain unchanged.

## What was compared

FULL uses the existing `PromptAssembler` byte for byte. SELECTED_EXPERIMENT first verifies the pinned full body and metadata sidecar, then creates a request-local bundle and citation validator. It preserves raw file segments and declared order. All eight policy documents remain mandatory. The only optional document is `records/places/gyeongbokgung.json`; an explicit 경복궁/Gyeongbokgung question or an unambiguously resolved reference includes it. Clearly supported policy questions and other backend places may omit it. The generic question vocabulary is deliberately narrow. Unknown intent, unsupported topics, override attempts and unresolved/ambiguous references fall back to the verified full bundle. Selection never uses prior assistant answers or fixture answer/expected-result fields.

The inventory was rechecked against current `packages/hanjeok/context-bundle.json` and `packages/explanation-rules.json`. Every bundled home of the current rules is retained. Policy documents: prompt; travel context; LLM/ranking boundary; course policy; congestion diagnosis; alternative scoring; why-this-place query; congestion grade values. The seed contains static place context rather than a policy rule. No mandatory policy was dropped to enlarge the reduction.

The seed's source file is **448 bytes**. Its serialized prompt segment, including marker and separator, is **501 bytes**. FULL has 24,230 source bytes / 24,703 serialized system bytes. The eight-document subset has 23,782 source bytes / 24,202 system bytes: 1.849% source-byte reduction and **2.028% system-byte reduction**. These are UTF-8 bytes, not tokens or billable usage.

## Results

29 versioned cases × 2 arms. Detailed rows, hashes, document paths and tool evidence are in [results.json](results.json). Fixtures include congestion, alternatives, visit order, no forecast coverage, unsupported weather/hours, multi-turn and positional references, poisoned answer history, ignore-rules requests, valid-but-unrelated citations, omitted seed citations, provider refusal/failure and tool success/failure/rejection.

| Arm/group | Cases | Documents | System UTF-8 bytes per request | Mean system-byte reduction |
| --- | ---: | ---: | ---: | ---: |
| FULL | 29 | 9 | 24,703 | 0% |
| SELECTED: fallback | 8 | 9 | 24,703 | 0% |
| SELECTED: real selection, optional included | 5 | 9 | 24,703 | 0% |
| SELECTED: real selection, optional omitted | 16 | 8 | 24,202 | 2.028% |
| All real selections | 21 | 8 or 9 | 24,202 or 24,703 | 1.545% |
| Entire SELECTED fixture suite | 29 | 8 or 9 | 24,202 or 24,703 | 1.119% |

Fallback rate: **8/29 = 27.586%**. Reasons: unsupported topic 2; unresolved reference 1; ambiguous reference 1; unknown intent 3 (including empty question and initial EXPLAIN without a question); override request 1. These rates depend on fixture composition, not production traffic. A fallback is never counted as a reduced selection.

| Check | Result | Meaning |
| --- | --- | --- |
| Required-policy retention | 8/8 = 100%, all 58 arm executions | No policy removal |
| Required-evidence document coverage | 100%, all executions | All paths declared by fixture authors remain present; not semantic truth |
| Selection determinism | 58/58 repeated selections, repeated whole report byte-identical | Same input yields same ordered system bytes |
| Omitted-seed citation probes | 16/16 rejected | Request validator cannot cite a removed document |
| Omitted-seed blocking + streaming fixtures | FULL accepts the present path; SELECTED rejects it | Path availability test, not model-quality ranking |
| Unrelated valid citation | Rejected in both arms | Current bounded congestion-topic rule requires the congestion policy; not general entailment |
| Poisoned prior answers | Selection unchanged | User questions/backend names resolve references, assistant answers do not |
| Successful tools | 2 cases per arm, successful results in facts union | Real AgentLoop wiring with scripted runner |
| Failed/rejected tools | 2 cases per arm, absent from facts union | Failure is sanitized; rejected arguments never execute |
| Corrupt/missing metadata, body/hash/inventory drift | Fail closed in tests before provider wiring | Never fall back to unverified data |
| Production singleton/body/wiring | Unchanged | Experiment is request-local and offline |

The provider always emits an authored answer (or authored failure), including deliberate invalid citations. It cannot measure how an actual model responds to omission or injection. Coverage, retention and determinism do not establish model accuracy or response quality. Actual token/cost/latency gains and cache effects remain unmeasured. Older model runs and October 9 health checks do not validate the current prompt/policy changes with an actual LLM.

## Reproduce and compatibility

```bash
./gradlew --offline test
./gradlew --offline offlineContextEval --args=docs/context-selection/results.json
./harness/scripts/check-wiki-compatibility.sh ../travel-context-wiki docs/context-selection/compatibility.json
```

The compatibility script regenerates body and metadata twice, checks byte-identical outputs against the agent's committed artifacts, and verifies all bundled rule homes remain mandatory. [compatibility.json](compatibility.json) records 9 docs / 24,703 bytes, body SHA-256 `ec60e6f912d16ec8d04b158504c99fc81b2c9edb6179c5da3cc0671a45b619c9`, and sidecar SHA-256 `62d758526e28fff443d21a9c4beb7d7f474031d5cd5698341bb1126a0af671eb`.

Fresh full server tests, bootJar and wiki smoke/index checks are recorded in [validation.json](validation.json). The frontend code is unchanged, so its build was not repeated. No push, PR, merge, deployment, credentials, SMTP, database/data updates or paid model evaluation occurred. The separate Hanjeok DB/SMTP rollout remains held.

## README images

[The code-based image specification](readme-diagram-spec.md) reviews the existing images and defines a two-input build/runtime picture plus three request lanes. New images are left to the parent task. README insertion anchors are present; historical SVGs are linked and no longer presented as current diagrams. No new image was generated or installed in this task.
