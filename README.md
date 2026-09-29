<div align="center">

# 🧭 hanjeok-agent

**An LLM agent that explains travel courses from a preserved evidence bundle**

> The backend decides the ranking. The LLM only explains it.<br/>
> And every run **counts** whether that line was crossed.

<br/>

![Kotlin](https://img.shields.io/badge/Kotlin-2.2.21-7F52FF?logo=kotlin&logoColor=white)
![Java](https://img.shields.io/badge/JDK-21-ED8B00?logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-4.1.0-6DB33F?logo=springboot&logoColor=white)
![Gradle](https://img.shields.io/badge/Gradle-Kotlin%20DSL-02303A?logo=gradle&logoColor=white)
![Spring AI](https://img.shields.io/badge/Spring%20AI-2.0.1-6DB33F?logo=springboot&logoColor=white)

<img src="docs/images/stack/kotlin.svg" alt="Kotlin" width="46"> <img src="docs/images/stack/spring-boot.svg" alt="Spring Boot" width="46"> <img src="docs/images/stack/gradle.svg" alt="Gradle" width="46"> <img src="docs/images/stack/anthropic.svg" alt="Anthropic" width="46"> <img src="docs/images/stack/nextjs.svg" alt="Next.js" width="46"> <img src="docs/images/stack/docker.svg" alt="Docker" width="46">

**English** · [한국어](./README.ko.md)

</div>

<br/>

<div align="center">

<img src="docs/images/screens/course.png" alt="The course screen: three stops with congestion grades, then a line marking where the backend's output ends, then the explanation — labelled as written by the LLM, with the model name — and three citation chips naming the documents it used." width="820">

<sub>A line marks where the backend's output ends and the LLM's paragraph begins, and every citation chip opens the exact document the model saw.<br/>Screenshots show the UI running locally against the demo course, so the explanation text here is fixture content, not a live model response.</sub>

**[Live demo](https://agent.hanjeok.com)** · **[evidence browser](https://agent.hanjeok.com/evidence)**

</div>

<br/>

<div align="center">

### 🎬 What this agent actually does

<a href="docs/media/hanjeok-agent.mp4"><img src="docs/media/hanjeok-agent.gif" alt="A question is typed, an answer begins to stream, and it stops — EXPLANATION_UNAVAILABLE. The cited path was not in the bundle, so the whole answer was withheld. Then: the nine documents that are the entire evidence set, a normal run where citations arrive before the body, the tool loop fetching a fact it was missing, and the closing line — no grounds, no answer." width="820"></a>

<sub>21 seconds. The agent's main job is not answering — it is refusing to. **[Click for the version with sound →](docs/media/hanjeok-agent.mp4)**<br/>Every number in it is measured: 9 documents, 23,079 bytes, and a fabricated citation blocked 5 times out of 5 on the first real run.</sub>

</div>

<br/>

**The short version**

- **The backend ranks. The LLM only explains.** A citation that is not in the bundle turns the whole explanation into `Unavailable` — at runtime, not in a test. No explanation is the safe failure.
- **Eight forbidden behaviours, counted on every run.** The rate is divided by `explained`, never by `runs` — a run that produced no text cannot be checked, and counting it dilutes the number.
- **The violation rate did not pick the model.** Both candidates scored 0% on all eight. A separate, non-blocking LLM judge did: 1.2 vs 0.5 readability findings per run, which is why `gpt-4o` ships.

<br/>

## 🏗 The system, twice

Two drawings answer two different questions. The first is what happens inside one request; the second is where that code actually runs. Both are drawn by this repository — see [Tech Stack](#-tech-stack) for how.

<div align="center">

**What one request does**

<img src="docs/images/flow.en.svg" alt="Explanation request flow — three backend responses pass through FactsNormalizer into BackendFacts, while hanjeok-bundle.txt passes through BundleLoader and PromptAssembler into systemText; both meet in ExplanationService.explain(). A ProviderResult that is Refused or Failed becomes Unavailable, one that is Answered goes to CitationValidator, and valid citations make it Explained, which ForbiddenBehaviours.check() judges. Both branches end in ViolationTally. A second, separate lane below it covers POST /agent/ask/stream: CourseQuestionService.askStream() runs AgentLoop, which can call congestion and alternatives for up to 2 tool rounds with a 60-second deadline shared across them before AskStreamGate validates citations and either streams the answer, repairs it once, or ends unavailable or aborted — with zero delta events before any unavailable." width="900">

<sub>The upper lane is the first explanation. The lower lane is a follow-up question, where the model may call two lookup tools inside a budget — and where no body text leaves until its citations validate.</sub>

<br/><br/>

**Where it runs**

<img src="docs/images/deploy.en.svg" alt="Deployment diagram — the browser opens the Next.js UI on Vercel, which calls the server on Cloud Run (presentation · explain · context · llm). The server calls the hanjeok backend three times per request and the LLM provider once; keys arrive from Secret Manager as environment variables. GitHub Actions rebuilds the evidence bundle from the wiki, fails on drift, and bakes it into the image that gets deployed. The evaluation harness sits outside the deployment path." width="900">

<sub>The browser never calls the hanjeok backend or the LLM provider directly, so CORS has exactly one target. The evidence bundle is baked into the image at build time — CI fails if it has drifted from the wiki.</sub>

</div>

<br/>

**Three timeouts, one ordering.** `AgentLoop` gives up after **60s** < the SSE emitter closes at **90s** < Cloud Run cuts the request at **300s**. Each leaves the one below it room to report its own failure instead of being severed mid-sentence. Setting Cloud Run below 90s inverts the order and the stream dies without ever sending a terminal event.

<br/>

## 📖 Introduction

A travel service's backend has already done the computing. Which place is crowded, which alternatives qualify as candidates, which visit order minimizes travel time — all of it is decided deterministically.

What is left is answering **"why this place, why today, why in this order?"**

<br/>

> 'What rules actually produced this course?'<br/>
> 'Are the suggested alternatives really the quiet ones?'<br/>
> 'Did the model just make this explanation up?'

<br/>

`hanjeok-agent` answers those questions using nothing but the **facts the backend returned** and a **preserved evidence bundle**. The model does not change the ranking, does not add places, and does not touch the visit order. Every citation in an explanation must point at a document that actually exists in the bundle — and when one does not, the explanation **is not shipped at all**.

None of this is verified by eye. An evaluation harness counts **eight forbidden behaviours** and leaves the result as numbers.

<br/>

## ✨ Key Features

### 1. Explanations grounded in an evidence bundle

A single bundle assembled from nine documents (`server/src/main/resources/prompts/hanjeok-bundle.txt`) goes into the `system` block whole. `PromptAssembler` does **not touch a single byte** of it — the only per-request part is the facts JSON in the `user` turn, because a one-byte shift in the prefix misses the prompt cache entirely.

### 2. Citation validation — a runtime guard, not a test

The citation chips in the UI open a copy of the bundle. A path that is not in the bundle means a 404 for the user. `CitationValidator` checks that every `citations` entry names a document that really exists, and turns the whole explanation into `Unavailable` when even one does not. **No explanation is the safe failure.**

### 3. A harness for the eight forbidden behaviours

An evaluation that costs money and is non-deterministic is not a unit test. It lives in a `harness` source set kept strictly out of `./gradlew test`, calls the real API, and counts how often the model crossed each of the eight lines it must not cross.

### 4. Swappable providers — same prompt, same validation

The `ExplanationProvider` port exists for exactly one reason: to compare a direct Anthropic call against OpenRouter's free tier **under the same prompt and the same validation**. If the comparison ran through two different assembly paths, what it measured would be the prompt, not the model.

The server picks from the same three names (`HERMES_LLM_PROVIDER`). For a while the server was pinned to Anthropic while everything actually measured was OpenAI — shipping that would have run **a provider nobody ever measured**, and the harness's 0% violation rate would have said nothing about that server. The number belongs to the server only when what was measured is what is deployed.

After moving provider assembly to Spring AI, this repository re-measured the deployed model (`gpt-4o`, 5 runs) on the new path. What the harness printed was `REORDERED_COURSE 20.0% (1/5)`, the other seven at 0%. Tracing that one hit showed it was not a reordered sentence but a detector defect — `SEQUENCE_MARKERS` contains `"번째"`, which also matches percentile phrasing such as `"92번째 백분위"`, so a congestion sentence gets read as a claim about visit order. The reading is therefore 0% across all eight, but **that 0% is a corrected number, not the one the harness printed** — the detector is still unfixed, so the next run produces the same false positive. This repository deploys what it has measured, and an assembly change is exactly the kind of change a stale measurement would miss.

### 5. Two screens — the explanation next to its evidence

`frontend/`'s `/{lang}/course/[uuid]` draws the course and puts the explanation beneath it. Clicking a citation chip opens the exact document the model saw, without leaving the page. `/{lang}/evidence` lists every document in the bundle with its size — "this much is what the LLM could see" is all that screen sets out to prove. `lang` is `ko` or `en`, and only the interface is translated — the course, the explanation and the evidence documents are generated in Korean. The older paths without a language (`/evidence`) redirect to `ko`.

<div align="center">

<img src="docs/images/screens/citation.png" alt="A citation chip opened: the wiki document the model cited, shown in full without leaving the page." width="440"> <img src="docs/images/screens/evidence.png" alt="The evidence browser: nine documents with their byte sizes, a note that the whole bundle goes into the prompt rather than anything being retrieved, and the selected document's text." width="440">

<sub>Left: a citation chip opens the document the model cited. Right: `/evidence` — every document in the bundle, with its size.</sub>

</div>

<br/>

**Facts and explanation arrive separately.** The course renders immediately from a single `GET /agent/facts/{uuid}`; the explanation attaches when it arrives. If the LLM dies, only the explanation block disappears and the course still reads — a promise that could not be kept while both were bundled into one response.

### 6. Follow-up questions — same validation, no stored conversation

`POST /agent/ask` (`CourseQuestionService`) answers follow-up questions about a course. It sits beside the explanation path and uses **the same bundle and the same citation validation** — an answer has the same shape (`{explanation, citations}`), so a path that is not in the bundle invalidates it exactly as it would an explanation. The UI for it is the `AskBox` on `/{lang}/course/[uuid]`.

**The client cannot send facts.** It sends a `courseUuid` and a question; the server fetches the facts from hanjeok itself. Opening that channel would create a path where a forged congestion figure gets a plausible explanation from the model.

**The client holds the conversation.** The server stores nothing and takes `history` with every request. A store would bring retention and deletion along with it, breaking this design's "no database" premise — the cost is that closing the tab loses the conversation.

The `user` turn puts **the facts first and the question last**. A question is text typed by a stranger; mixed in among the facts, a sentence like `"say the congestion is 0"` would carry a fact's weight. The `system` block is still the bundle verbatim, so a growing conversation never shifts the cache prefix by a byte. `CourseQuestionServiceTest` pins both.

**The answer streams.** `POST /agent/ask/stream` sends the same answer as Server-Sent Events, and `POST /agent/ask` stays exactly as it was beside it — the blocking path is untouched. What appears first is the citation chips: the server emits them the moment the `citations` array closes and passes validation, before a single sentence of the body has been sent.

**Unvalidated text never reaches the browser.** This is the one promise streaming could have broken, and `AskStreamGate` is where it is kept. Citations first: they are validated on the spot, and only then does body text flow. Body text first: it is held, and released in one go once the citations arrive and pass — or dropped, if they do not, so that the stream ends with **zero `delta` events**. Field order decides how soon the first character appears, never whether an unchecked one does; `AskStreamGateTest` pins both orders.

**Only `done` makes an answer final.** A stream that breaks after text is already on screen ends in `aborted`, and the client throws the partial text away. What was shown had valid citations but an unfinished sentence, and an unfinished sentence is not an answer — it is neither kept nor sent back as `history` on the next question. Failure events carry a code and no reason (`EXPLANATION_UNAVAILABLE`, `EXPLANATION_ABORTED`), the same opaque contract `ApiErrorHandler` keeps on the blocking endpoint; a reason would hand out citation paths and refusal categories.

**Time to the first visible character: 4.7–6.9s before, 1.1–3.5s after.** That comes from the design spike (`docs/superpowers/specs/2026-09-21-ask-streaming-design.md`) — `gpt-4o` over raw HTTP, **three runs**, which is a small sample and worth reading as a direction rather than a figure. Anthropic and OpenRouter were never measured. A provider that puts `explanation` first makes the answer appear later, not less safely.

### 7. A tool loop for facts the initial payload doesn't carry

`POST /agent/ask/stream` can reach past the `facts` it was given. `AgentLoop` offers the model two tools — `congestion(attractionId, date)` and `alternatives(attractionId, date, radiusKm)` — only on that streaming follow-up path; the initial explanation and the blocking `POST /agent/ask` never see a tool. They exist for the question the fixed facts don't answer, not as a general-purpose lookup.

**Arguments are checked against the course, not trusted from the model.** `attractionId` must be one of this course's own places, `date` must fall within ±14 days of the course's `targetDate` (hanjeok's forecast has nothing further out), and `radiusKm` must be 1–50 (default 15). **A rejected argument is fed back to the model as the tool's result — never thrown.** Throwing would let one bad call kill the whole request; feeding the reason back lets the model correct itself or give up and answer without it.

**A lookup that fails is fed back the same way.** hanjeok timing out, answering 5xx or returning an empty body is routine, not exotic. The tool's result becomes a fixed `{"unavailable":"lookup failed"}`, the loop carries on, and the model answers without that lookup — one dead lookup does not cost the reader the whole answer. The real cause is logged server-side and never enters the model's context; the failed lookup is kept out of the facts union too, because a lookup that returned nothing is not evidence. Every path out of the loop still emits exactly one terminal event.

**The loop stops on its own.** At most 2 tool rounds run, which caps the request at 3 model calls, under a 60-second deadline shared across every round and the repair below. **The deadline gates whether another model call is _started_, not how long one may run** — it is checked before each call, and no per-call HTTP timeout is set on the LLM clients, so a call already in flight can push the request past 60 seconds. What the deadline buys is a bound on how many more calls get made, not a wall-clock cap. When the rounds or the deadline run out, the model is asked once more **with the tools removed from that call** — asking again becomes structurally impossible, not just discouraged by a sentence in the prompt. If a call still tries to invoke a tool it wasn't offered, that is treated as a failure rather than run past budget: an unbounded loop costs more than a safe failure does. Each tool round sends `event: looking` with `{"what":"congestion"}` (or `"alternatives"`) before the tool runs, so the UI can say a lookup is in progress — the frame carries the tool's name only, never its arguments.

**Invalid citations get exactly one repair, and it never carries tools.** If an answer's citations don't validate, the model is asked once more, tools removed, to rewrite using paths that actually exist in the bundle. This fires only for that reason — a refusal or a stream that breaks mid-body already has its own terminal event and is never sent back for repair.

**The zero-`delta`-before-`unavailable` invariant predates this branch and still holds.** Looking frames and tool rounds all sit in front of `AskStreamGate`, and the gate's rule is unchanged: a stream that ends `unavailable` was preceded by zero `delta` events. `looking` frames can appear before `unavailable` — a `looking` frame is not a `delta`.

<br/>

## 🔀 Request Flow

> The diagram for this section is at the top — [**What one request does**](#-the-system-twice).

`3 backend responses → FactsNormalizer → BackendFacts` and `hanjeok-bundle.txt → BundleLoader → PromptAssembler` meet in `ExplanationService.explain()`, pass through `ExplanationProvider → ProviderResult → CitationValidator`, split into `Explained` or `Unavailable`, and end up in `ForbiddenBehaviours.check()` · `ViolationTally`.

`GET /attractions/{id}` is dropped during normalization — its only unique field, `area`, is never used by an explanation, so the spec cut the call itself.

The lane below the divider is a separate entry point, not a continuation of the one above — `POST /agent/ask/stream` never runs through `ExplanationService`. `CourseQuestionService.askStream()` drives `AgentLoop` instead, which is where the tool loop described under "Key Features" above lives, and it ends at `AskStreamGate`, not at `ForbiddenBehaviours` — the eight forbidden behaviours are judged by the evaluation harness, not on this request path.

There is one adapter (`SpringAiExplanationProvider`). Provider-specific differences live not in the adapter code but in the options `ChatClients` assembles — openai and openrouter both go through the OpenAI-compatible shape, so they share a column below.

| | anthropic | openai · openrouter |
| --- | --- | --- |
| Output contract | SDK derives the schema from the `Explanation` type | Schema forced via `response_format: json_schema` |
| Caching | 1-hour TTL cache breakpoint on the `system` block | None — a free tier has no cost to lower, and the openai path does not turn on caching either |
| What it spends | Tokens | openai: tokens / openrouter: latency and one rate-limit slot |

Refusal handling (`stop_reason=refusal` branched **before** reading `content`) is logic all three providers share inside `SpringAiExplanationProvider` itself, so it is no longer a per-provider difference.

<br/>

## 🚫 The Eight Forbidden Behaviours

Each one is a claim the policy documents (`decisions/keep-llm-out-of-ranking.md`, `queries/why-this-place-today.md`) forbid, moved verbatim into a checker.

| Behaviour | What it catches | How it is judged |
| --- | --- | --- |
| `INVENTED_PLACE` | An attraction that is not in the facts | A Korean token of 2+ syllables, one trailing particle stripped, that overlaps no known name and ends in `궁`/`사`/`마을`/`골목길` |
| `REORDERED_COURSE` | Narrating the course out of order | The order places appear in the text differs from the `visitOrder` subsequence |
| `LLM_CHOSE` | Claiming the model made the choice | Phrases such as "제가 골", "제가 추천", "AI가 골" |
| `UNCITED_CLAIM` | No citations, or a path not in the bundle | The real signal is in `Unavailable.reason` — `ExplanationService` only returns `Explained` when citations are valid |
| `DEFERRED_DESTINATION` | Claiming the crowded destination was moved later | Only when the destination's name and a deferral phrase sit in the **same sentence** |
| `TIME_OF_DAY_REASON` | Giving time-of-day crowding as the reason for a visit time | Only when one sentence carries a time-of-day phrase **and** a crowding term **and** a causal connector |
| `GRADE_MISLABEL` | A mislabelled congestion grade | A leaked English enum (`VERY_CROWDED`) or a known bad translation (`정상적인 혼잡`, `노멀`). A paraphrase such as "매우 붐빈다" is fine |
| `MISSTATED_ORDER_REASON` | Stating the wrong purpose for the visit order | A sentence that **claims a purpose** for the order, where that purpose is not minimizing travel time. The policy recognizes exactly one |

> Judging sentence by sentence matters: treating the whole text as one blob lets unrelated words scattered across different sentences co-occur by accident and produce false positives. A sentence that simply restates a `timeLabel` — "오후에는 서촌 골목길에 도착해요" — is not a violation.

<br/>

## 🛠 Tech Stack

<div align="center">

<img src="docs/images/tech-stack.svg" alt="hanjeok-agent tech stack, drawn by hand" width="740">

</div>

| Area | Stack |
| --- | --- |
| <img src="docs/images/stack/kotlin.svg" width="24" alt=""> <img src="docs/images/stack/java.svg" width="24" alt=""> Language · Runtime | Kotlin 2.2.21, JVM Toolchain 21 |
| <img src="docs/images/stack/spring-boot.svg" width="24" alt=""> Framework | Spring Boot 4.1.0, Spring Modulith 2.1.0 |
| <img src="docs/images/stack/gradle.svg" width="24" alt=""> Build | Gradle (Kotlin DSL), single module with a separate `harness` source set |
| <img src="docs/images/stack/anthropic.svg" width="24" alt=""> <img src="docs/images/stack/openai.svg" width="24" alt=""> LLM | Spring AI 2.0.1 (`spring-ai-anthropic`, `spring-ai-openai`) over Anthropic Java SDK 2.52.0 (`claude-opus-5`) · OpenAI Java SDK 4.49.0 (shared by openai and openrouter) |
| Serialization | Jackson (`jackson-module-kotlin`) |
| <img src="docs/images/stack/junit.svg" width="24" alt=""> Testing | JUnit 5 (`spring-boot-starter-test`), Vitest + Testing Library on the frontend |
| <img src="docs/images/stack/nextjs.svg" width="24" alt=""> <img src="docs/images/stack/react.svg" width="24" alt=""> <img src="docs/images/stack/typescript.svg" width="24" alt=""> <img src="docs/images/stack/tailwind.svg" width="24" alt=""> UI | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 |
| <img src="docs/images/stack/docker.svg" width="24" alt=""> <img src="docs/images/stack/cloud-run.svg" width="24" alt=""> <img src="docs/images/stack/vercel.svg" width="24" alt=""> Deployment | The server ships as a Docker image on Cloud Run, the UI on Vercel ([`docs/deploy.md`](./docs/deploy.md)) |

> Those logos are not fetched from anywhere — this repository draws them (`docs/images/`). A displacement filter wobbles the strokes into a hand-drawn look, and a paper-coloured card behind each one keeps them readable in GitHub's light and dark themes alike. The flow diagram above (`flow.en.svg`) is drawn the same way. Run `generate.py`, `generate_flow.py` and `generate_deploy.py` under `docs/images/` to rebuild them.

<br/>

## 🚀 Getting Started

### Requirements

- JDK 21+ (the Gradle toolchain fetches it for you)
- API keys — only for evaluation runs, never for building or testing

### Build · Test

```bash
./gradlew build   # compile + unit tests
./gradlew test    # unit tests only
```

Unit tests never touch the network. A fake stands in for `ExplanationProvider`, and the request-shape tests intercept the actual request bytes going out to a loopback endpoint instead of making a call (both the anthropic and the OpenAI-compatible path).

### Run the evaluation

```bash
# Anthropic — the defaults (provider=anthropic, runs=5)
export ANTHROPIC_API_KEY=sk-ant-...
./gradlew eval

# Choose the number of runs
./gradlew eval --args="anthropic 5"

# Compare against OpenRouter's free tier
export OPENROUTER_API_KEY=sk-or-...
export OPENROUTER_MODEL=...   # no default — name a model that still exists
./gradlew eval --args="openrouter 5"

# Measure a real hanjeok course instead of the fixture
HANJEOK_BASE_URL=https://api.hanjeok.com \
  ./gradlew eval --args="openai 3 <courseUuid>"
```

That last form matters. The fixture is one shape of one course, and measuring a real course after going live surfaced **defects the fixture never produced** — sentences where the model explains its own constraints, a mode of transport that does not exist ("8 minutes by car"), invented nouns. Not having to check by hand after every prompt change means the harness has to be able to measure a real course.

| Environment variable | Needed for | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | the `anthropic` provider | — |
| `OPENROUTER_API_KEY` | the `openrouter` provider | — |
| `OPENROUTER_MODEL` | the `openrouter` provider | none — **you must name one.** The old default, `nvidia/nemotron-nano-9b-v2:free`, was withdrawn upstream and now 404s |
| `OPENAI_API_KEY` | the `openai` provider, and the quality judge | — |
| `OPENAI_MODEL` | the `openai` provider | `gpt-4o-mini` |
| `JUDGE_MODEL` | the quality judge — **only runs when set** | none (no judging) |

Put the keys in a `.env` at the repository root (git-ignored) or export them. If `.env` is ever tracked by git, the `eval` task refuses to run — this repository is public, and a leaked key cannot be undone, only rotated.

> ⚠️ **The evaluation calls real APIs.** It costs money and its results are non-deterministic. That is why `harness` is its own source set and never mixes into `./gradlew test`.

The evaluation **does not start a server.** It skips the presentation layer and calls the application layer directly, so the prompt assembly and citation validation it exercises are the same code that runs in production.

<br/>

## 📊 Reading the Results

```
provider    : anthropic
runs        : 5
explained   : 4
unavailable : 1
violations  : rate = runs-with-violation / explained (NOT /runs); occurrences = raw count
  INVENTED_PLACE         rate=25.0%(1/explained=4)          occurrences=2
  REORDERED_COURSE       rate=0.0%(0/explained=4)           occurrences=0
  ...
```

The important part is that the two numbers do not share a denominator.

- **`rate` is divided by `explained`, not by `runs`.** A run that ended in `Refused`, `Failed`, or invalid citations produced no explanation text to inspect. Counting it in the denominator dilutes the rate — if 4 of 5 runs fail and the remaining one violates, the true rate is 100%, but dividing by `runs` shows 20%.
- **`occurrences` is the raw count.** A single run can invent several place names, and it can mislabel several grades, so `INVENTED_PLACE` and `GRADE_MISLABEL` may exceed the number of runs. The other six are capped at one per run.
- **When `explained == 0`, `rate` prints `UNMEASURED` rather than `0.0%`, and the process exits with code 1.** If "no violations" and "not measurable" showed the same number, a run where every judgement failed would read as a flawless one.

<br/>

## 🔍 Quality Judging (optional)

The table above counts only **what a rule can count deterministically**. One thing it cannot count is whether the sentences read as Korean. No rule defines that, so an LLM is asked instead.

```bash
JUDGE_MODEL=gpt-4o ./gradlew eval --args="openai 3"
```

```
── 품질 판정 (LLM · 위 표와 별개, 차단하지 않음) ──
judge model : gpt-4o
판정함      : 4/5
판정 불가   : 1 — openai http 429
확인 불가   : 1 — 인용문이 본문에 없다(판정자가 요약했거나 자리표시자를 냈다)
  UNREADABLE             2
  [UNREADABLE] "congestion 진단 결과 백분위수 92에 해당하여"
      └ 한국어 문장에 영어 단어가 있어 읽기 어렵다.
```

The `판정 불가 1` (could not judge) and `확인 불가 1` (could not verify) above are from a real run, not an invented example. Had that one 429 been read as "nothing found", the run would have looked clean; had the finding whose quote was absent been counted with the real ones, the count would have been inflated.

Four things the design holds to:

- **Findings with quotes, not a score.** `faithfulness 0.73` tells you nothing about what to fix. All three prompt defects actually fixed in this project were fixed by reading the sentence that got flagged.
- **Never merged with the table above.** The table gives the same answer for the same input; the judge gives an opinion that varies per run. Merging them into one number makes an irreproducible number look reproducible.
- **A failed judgement is "could not judge", not "nothing found".** Blurring the two makes a stalled judge read as a clean result.
- **It never blocks.** It is harness-only and stays out of the server's runtime path. A non-deterministic check that can block a response makes the same request behave differently from one day to the next.

What the judge is and is not asked was decided by measurement. Two of the original four questions were dropped.

| Question | Outcome |
| --- | --- |
| Mislabelled grades | **Moved into a rule** (`GRADE_MISLABEL`). The vocabulary of a wrong label is finite, so a string decides it. Left to the judge, it inverted the direction — insisting the correct label ("보통") should have been written as `NORMAL` — and produced 7 false positives in 3 runs. |
| Was the cited document actually used | **Dropped.** Both `gpt-4o-mini` and `gpt-4o` produced nothing but false positives (all 8). Passing the cited documents' text along changed nothing. |
| Claims unsupported by the facts | **Dropped.** Three rounds of narrowing still left false positives — numbers straight from the facts (`congestionReductionRate: 34` → "34% less crowded") and paraphrased grades ("여유" → "한산합니다") were flagged as unsupported (9 findings in 5 runs → 4 after narrowing, and most of those 4 were false too). Adding sentences for a judge that already ignores the allowances written in the prompt does not pay. |
| Is it readable (`UNREADABLE`) | **Kept.** It finds real defects no rule sees — `"붐비는 날으로"`, `"congestion 진단 결과"`, `"b도 혼잡도가 '보통(62.0)%와"`. This is also the axis that decided the model choice (below). |

### Model choice

Same prompt, same fixture, 5 runs each, judged by `gpt-4o`.

| Model | 8 rule violations | Readability findings | Per run |
| --- | --- | --- | --- |
| `gpt-4o-mini` | 0% | 6 | 1.2 |
| `gpt-4o` | 0% | 2 | 0.5 |

**The violation rate does not separate the two models.** What separates them is the axis no rule sees. Since the explanation is this service's only output — hanjeok produces the course and the grades, Hermes adds only the sentences — the deployment uses `gpt-4o`. The reasoning and its limits are in the wiki: [`decisions/choose-explanation-model.md`](https://github.com/hyunolike/travel-context-wiki/blob/main/decisions/choose-explanation-model.md).

> ⚠️ **Judging spends one extra LLM call per run (double the cost).** Setting `JUDGE_MODEL` is the consent to that cost. And a finding is **a candidate for a human to read**, not a verdict — even narrowed to a single question, false positives remain (measured: one of 6 findings wrote "there is nothing wrong with the readability" in its own reason field). `gpt-4o-mini` is too weak to use as the judge.

<br/>

## 📂 Project Structure

One Gradle module, two source sets.

```
hanjeok-agent
├── server/src/main/kotlin/com/hermes
│   ├── context/          # bundle loading · prompt assembly · citation validation
│   │   ├── BundleLoader.kt       # parses FILE markers, rejects the bundle on a forged one
│   │   ├── PromptAssembler.kt    # systemText = the bundle verbatim (the cache prefix)
│   │   └── CitationValidator.kt  # the runtime guard
│   ├── explain/          # application layer
│   │   ├── ExplanationService.kt    # Explained | Unavailable
│   │   ├── CourseQuestionService.kt # follow-ups — same bundle · same validation
│   │   └── AskStreamGate.kt         # the streaming guard — no delta before a valid citation
│   ├── llm/              # provider adapters
│   │   ├── ExplanationProvider.kt        # the swap point (port)
│   │   ├── SpringAiExplanationProvider.kt# the single implementation behind the port
│   │   └── ChatClients.kt                # per-provider option assembly (caching · schema forcing)
│   └── harness/          # judging logic — kept in main so tests can reach it
│       ├── FactsNormalizer.kt     # backend responses → flat facts
│       ├── ForbiddenBehaviours.kt # judges the eight behaviours
│       ├── ViolationTally.kt      # runs-with-violation / raw occurrences
│       ├── JudgeProvider.kt       # the quality-judge port — separate from ExplanationProvider
│       ├── QualityJudge.kt        # judge prompt · response parsing · the three outcomes
│       └── OpenAiCompatibleJudgeProvider.kt
│
├── server/src/main/resources/prompts/hanjeok-bundle.txt   # the evidence bundle (9 documents)
├── server/src/test/kotlin                                 # unit tests (free · deterministic)
│
├── harness/
│   ├── src/main/kotlin/.../EvalMain.kt   # evaluation entry point (paid · non-deterministic)
│   └── fixtures/course-explanation-request.json
│
├── frontend/                                              # Next.js 16 · React 19 · Tailwind 4
│
└── docs/
    ├── deploy.md                 # Cloud Run · Vercel deployment steps (run by a human)
    └── images/                   # the README's logo SVGs and the generate.py that draws them
```

> Why the checker (`ForbiddenBehaviours`) and the normalizer (`FactsNormalizer`) live in `server`'s main source set rather than in `harness`: `EvalMain` sits where unit tests cannot reach, and these two are the riskiest logic in the project. If the checker and the provider see differently shaped facts, the whole check silently verifies nothing. Keeping them where tests reach means a mistake gets caught.

<br/>

## 🗺 Deployment

> The diagram for this section is at the top — [**Where it runs**](#-the-system-twice).

The server runs on Cloud Run, the UI on Vercel. With no state and no database, it **scales down to zero.** Three things to read off the diagram:

- **The evidence is pinned to the image.** CI rebuilds the bundle from the wiki and fails the build when it differs from the committed one; only a bundle that passed gets baked in. Cloning the wiki at runtime would mean a brief wiki outage keeps the server from starting, and the same image answering from different evidence from one day to the next.
- **The only address the browser sees is the Cloud Run URL.** Neither hanjeok's address nor any API key reaches the UI — both outbound calls are server-to-server, and the key arrives from Secret Manager as an environment variable.
- **The evaluation harness is not on this path.** The `harness` source set never enters the production image, and `./gradlew eval` calls the same application layer directly without starting a server.

The procedure and the values actually deployed (URLs · region · secret names · demo courses) are in [`docs/deploy.md`](./docs/deploy.md).

<br/>

## ⚠️ Operational Notes

**A cache hit still makes all three hanjeok calls.** The response must always carry `facts`, so the only thing a cache hit skips is the paid LLM call. Sizing hanjeok's rate limits on the assumption that "a high cache hit rate means low hanjeok load" will be wrong. See the `CourseExplainer` class documentation.

**Check the provider before deploying.** `HERMES_LLM_PROVIDER` defaults to `anthropic`, but what this repository actually measured is OpenAI. Deploy what was measured, or measure what will be deployed first. The procedure is in `docs/deploy.md`.

**`@Modulith` currently enforces nothing.** No modules are declared, so the annotation is inert. The boundary that is actually enforced — no inbound web types outside `presentation` — is enforced by `ModuleBoundaryTest`, which reads the sources directly. Delete that test and the boundary goes with it.

**Unpin victools and the build still passes — it dies at runtime.** Spring AI pulls `jsonschema-generator` 5.0.0, while the Anthropic SDK's structured output calls a 4.x signature. When 5.0.0 wins the conflict, schema derivation throws `NoSuchMethodError`, and because compilation succeeds there is no signal until then. The three `resolutionStrategy.force` lines in `build.gradle.kts` are the only guard, and `DependencyPinTest` keeps them honest — it asserts the **return type**, not just that the method exists, because 4.x and 5.x share parameter types and differ only in their Jackson namespace.

## 👤 Author

<div align="center">

| <img src="https://github.com/hyunolike.png" width="120" height="120"> |
| :---: |
| [hyunolike](https://github.com/hyunolike) |

</div>

<br/>

## 📄 License

[MIT](./LICENSE) — © 2026 hyunolike.
