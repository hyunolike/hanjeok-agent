<div align="center">

<a href="https://agent.hanjeok.com"><img src="docs/media/hanjeok-guide.jpg" alt="Hanjeok Agent — a green leaf scout holding a card, above the name and the address agent.hanjeok.com" width="820"></a>

# Hanjeok Agent

**Ask where it's crowded. See where the answer came from.**

A travel guide agent for the [Hanjeok](https://hanjeok.com) service. It looks things up in steps you can watch,<br/>
and answers citing only what it fetched for your question.

**English** · [한국어](./README.ko.md) · [日本語](./README.ja.md) · [中文](./README.zh.md)

[![Live demo](https://img.shields.io/badge/Live_demo-agent.hanjeok.com-172033?style=for-the-badge&logo=googlechrome&logoColor=white)](https://agent.hanjeok.com/en/ask)

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5.26-4581C3?logo=neo4j&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Cloud_Run-4285F4?logo=googlecloud&logoColor=white)

</div>

<br/>

<div align="center">

<a href="docs/media/hanjeok-guide.mp4"><img src="docs/media/hanjeok-guide.gif" alt="A question is asked on the live site. Steps appear one by one, then an answer with a citation chip, then the path of ranked alternatives, then the evaluation table." width="760"></a>

<sub>20 seconds, captured from the live site on real Hanjeok data. <b><a href="docs/media/hanjeok-guide.mp4">Watch with sound →</a></b></sub>

</div>

<br/>

## 🧭 The question this answers

"Somewhere quiet instead of Gyeongbokgung this Saturday?"

A search box cannot answer that. It takes three things in a row: find the place, check how crowded it is forecast to be on that date, then ask which alternatives the service ranks for it. And once an answer comes back, a second question follows: **who says so?**

| A chat box over a database | Hanjeok Agent |
| :-- | :-- |
| The model writes an answer and you take its word | Every step it took is on screen, with what each one fetched |
| The model picks what sounds good | The service ranks; the model never reorders or chooses |
| A fluent answer may rest on nothing | An answer may cite only what this question fetched, or it is not shown |
| "No data" quietly becomes "probably fine" | A place with no forecast is reported as unknown, never as quiet |

<br/>

## ✨ What you can do

<table>
  <tr>
    <td width="52%" valign="top"><img src="docs/images/guide/screens/steps.png" alt="The ask screen while a question is being worked on: two finished steps, reading the question and finding the place."></td>
    <td valign="top">

### Ask, and watch it work

- Ask in your own words, with a place and a date.
- The question is read **by rule first**: which place, which date, and whether it is something the agent answers at all. No model is called for that.
- Each lookup appears as it finishes. A lookup that was refused is shown too, with the reason.

</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/images/guide/screens/answer.png" alt="An answer card with one citation chip labelled Hanjeok record."></td>
    <td valign="top">

### Get an answer you can check

- Citations come in two kinds: a **Hanjeok record** for a fact, a **policy document** for why the service treats it that way.
- An answer is checked before it is shown. Citing something that was not fetched for this question fails the check; after one repair attempt, nothing is shown.
- Prices, opening hours and "reorder the ranking for me" are declined, with a sentence saying what can be asked instead.

</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/images/guide/screens/path.png" alt="The path view: Gyeongbokgung at the top, alternatives numbered in rank order below it, regions on the right, policy documents on the left."></td>
    <td valign="top">

### See the path it took

- The places, links and documents the answer touched, as a drawing and as a list.
- Alternatives are **in the order Hanjeok ranked them**. The screen does not re-sort.
- It shows exactly what was fetched. Nothing is added to make the picture fuller.

</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/images/guide/screens/eval.png" alt="The evaluation page: a scores table where unscored cells say Not scored with a reason."></td>
    <td valign="top">

### Read how well it does

- Two retrieval strategies answer the same questions: **text similarity only**, and **plus relatedness links**.
- Every score carries the number of questions behind it.
- A score that could not be computed says **"Not scored"** and why. It is never a zero.

</td>
  </tr>
</table>

Also: [browse a place's neighbours](https://agent.hanjeok.com/en/graph?place=653) without asking anything.

<br/>

## ⚙️ How one question is handled

<div align="center">
<img src="docs/images/guide/question-flow.png" alt="Six numbered steps left to right: Question, Read by rule, Choose a lookup, Write the answer, Citation gate, Answer plus citations plus path. Read by rule can exit to Declined or to Which one do you mean. Choose a lookup loops through Run it in code, which reaches the Neo4j graph and the Hanjeok API. The citation gate can send the answer back once for repair, and refuses twice means nothing is shown." width="820">
</div>

Five rules hold across every path through that picture.

1. **The model does not write queries.** It picks one of seven lookups; code validates the inputs and runs a fixed read.
2. **The model does not rank.** Lists arrive numbered in Hanjeok's order and are passed on in that order.
3. **A place cannot be reached by guessing its id.** A lookup accepts only places this question has already found.
4. **Unverified text never reaches the screen.** The answer is sent whole, after the citation check, not streamed token by token.
5. **The budget is fixed.** Three lookup rounds, one answer, one repair, sixty seconds.

<br/>

## 🏗 System architecture

<div align="center">
<img src="docs/images/guide/architecture.png" alt="Four columns: the visitor's browser, Next.js screens on Vercel, one Cloud Run container holding FastAPI, an MCP server, the LangGraph agent, seven validated lookups, the citation gate, Neo4j and the embedding model, and outside services NVIDIA NIM and the Hanjeok API. A strip along the bottom shows build time: Hanjeok DB, export script, JSONL plus manifest, verify, graph built into the image." width="820">
</div>

**The agent holds no credentials to Hanjeok's database.** Data crosses over in two ways only:

- **Slow-changing data, as a file.** A script on the Hanjeok side exports public tourism tables with an allow-list of columns. The agent verifies hashes, row counts and columns, and refuses the whole file if a column it does not expect appears. The graph is built from that file when the container image is built.
- **Date-bound data, at question time.** Congestion forecasts and alternatives come from two read-only Hanjeok endpoints. The place-detail endpoint is never called, because it records a view on every call.

Three parts are libraries rather than this repository's own code: LangGraph's stream, `interrupt` and checkpointer carry the steps, the "which place do you mean?" pause, and a visit's earlier questions; neo4j-graphrag's `VectorCypherRetriever` does the similarity search; and an MCP server exposes four read-only tools so another program, eventually the Hanjeok backend, can ask the agent.

<br/>

## 📊 What has been measured

Small, and stated as such.

| | |
| :-- | :-- |
| **Data in the deployed service** | 13,403 places, 45,244 relatedness links, 353 events, exported from Hanjeok on 2026-10-14 |
| **Tests** | 408 backend (no network, no key), 16 against a real Neo4j, 246 frontend |
| **Waking from zero** | about 30 seconds (Neo4j 19 s, server 10 s) |
| **One question, once awake** | 6 to 9 seconds; up to 56 seconds when the model provider rate-limits |

The published evaluation is **sixty questions over Hanjeok's real data** (the 2026-10-14 export), ten of each of six kinds, without the RAGAS judge. Hanjeok's forecasts and alternatives were recorded once and replayed. Each strategy answered 41, declined 12 and failed on 7.

| | Text similarity only | Plus relatedness links |
| :-- | :-: | :-: |
| Share of needed records fetched | 0.725 (50 questions) | 0.86 (50 questions) |
| Same, for questions about two or more linked places | 0.025 (10 questions) | 0.60 (10 questions) |
| Unanswerable questions declined | 10 of 10 | 10 of 10 |
| Forbidden behaviours counted, over 60 answers | 9 | 4 |

Most of the forbidden counts are uncited claims (6 and 3). Record precision is 0.23 and 0.27; it is low by construction, since the place records and policy documents fetched alongside also count, and it is only meant to compare the two. The earlier twelve questions over invented places stay in the repository for tests.

> [!NOTE]
> **Not done yet: RAGAS scores.** The judge ran once on the shared model key and got an answer to 1 of 72 requests; the rest were rate-limited. The page shows those cells as "Not scored".

> [!WARNING]
> **Wrong answers have passed the citation check.** On real data the agent once said alternatives were listed "nearest first" (they are in Hanjeok's score order) and once called a beach "quiet today" without having fetched its forecast. Both cited records that were really fetched; the claims went beyond them. Two forbidden-behaviour rules now catch these cases, and the agent sends such an answer back to be rewritten once. In the sixty-question run both rules counted 0.

<br/>

## 🛠 Tech stack

| Area | What is used |
| :-- | :-- |
| Agent service | Python 3.13 · FastAPI · LangGraph (stream, `interrupt`, checkpointer) · LangChain |
| Graph and search | Neo4j 5.26 · neo4j-graphrag `VectorCypherRetriever` · multilingual-e5-large (1024-d, local) |
| Model | NVIDIA NIM nemotron, structured output |
| Other programs | MCP server, four read-only tools |
| Evaluation | RAGAS · id-based precision and recall · eight rule-based forbidden-behaviour counters |
| Screens | Next.js 16 · React 19 · Tailwind 4 |
| Deployment | Cloud Run (service and Neo4j in one container) · Vercel · Cloud Build |
| Tracing | Langfuse, off unless its keys are set |

<br/>

## 🗂 Repository tour

| Path | What it is |
| :-- | :-- |
| [`bench/src/guide/`](bench/src/guide/) | The agent: scope rules, lookups, LangGraph loop, citation gate, API, MCP server, evaluation |
| [`bench/tests/`](bench/tests/) | Unit, contract and Neo4j integration tests; a synthetic export of invented places |
| [`bench/Dockerfile`](bench/Dockerfile) · [`bench/deploy/`](bench/deploy/) | The image that carries the service, Neo4j and a pre-built graph |
| [`frontend/`](frontend/) | The four screens |
| [`specs/002-hanjeok-guide-agent/`](specs/002-hanjeok-guide-agent/) | Specification, research decisions, data model, contracts, tasks |
| [`docs/prd/`](docs/prd/hanjeok-guide-agent.md) | Product requirements (Korean) |
| [`docs/deploy.md`](docs/deploy.md) | How it was deployed, with the commands that were run |
| [`server/`](server/) | The earlier course explainer (Kotlin, Spring AI) — see below |

### Where to read the core ideas in code

- [`scope.py`](bench/src/guide/scope.py) — what is decided about a question before any model is asked
- [`lookups.py`](bench/src/guide/lookups.py) — the seven lookups and what each refuses
- [`agent.py`](bench/src/guide/agent.py) — the LangGraph loop, the pause, the budgets
- [`citations.py`](bench/src/guide/citations.py) — the gate
- [`export.py`](bench/src/guide/export.py) — refusing an export that is not what its manifest says
- [`forbidden.py`](bench/src/guide/forbidden.py) — eight behaviours counted by rule

<br/>

## 🚀 Run it locally

Screens only, replaying recorded responses. Needs Node 22 and pnpm.

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000/en/ask
```

The service, on the synthetic export. Needs Python 3.13, uv and Docker.

```bash
cd bench
docker compose up -d
uv sync
uv run guide refresh --export tests/fixtures/hanjeok-export
GUIDE_LIVE_MODE=replay uv run uvicorn guide.api:app --port 8090   # NVIDIA_API_KEY needed to answer

uv run pytest                    # 408 tests, no network
uv run guide mcp                 # the same agent over MCP (stdio)
```

Then point the screens at it: `NEXT_PUBLIC_GUIDE_BASE_URL=http://localhost:8090 pnpm dev`.

<br/>

## ⚠️ Known limits

- **A first question after idle waits about 30 seconds.** The service scales to zero; the screen says it is waking.
- **The model key is shared with other projects.** A rate limit slows a question or fails it.
- **Two-character place names are matched conservatively.** "지도" (also an island) in "show me on the map" still reads as the island.
- **Visits and usage limits live in memory.** The service runs as one instance for that reason.
- **The guide character's images** were generated with Codex image generation. Trademark and AI-copyright review was not performed; the author released them on 2026-10-14. See [`provenance.json`](design/guide-character/v1/provenance.json).

<br/>

## 📚 The earlier component: course explainer

Before the guide agent, this repository explained one thing: a travel course the Hanjeok backend had already built, on the screen where it is shown. That service (Kotlin, Spring AI) still runs at [agent.hanjeok.com](https://agent.hanjeok.com) and its write-up, with the harness that counts eight forbidden behaviours and the model comparison that picked `gpt-4o`, is kept in full:

**[Course explainer README →](docs/explainer/README.md)** · [한국어](docs/explainer/README.ko.md)

<br/>

## 👤 Author

<div align="center">

| <img src="https://github.com/hyunolike.png" width="120" height="120"> |
| :---: |
| [hyunolike](https://github.com/hyunolike) |

</div>

Built as the project for a full-stack open-source AI agent course (2026). Open follow-ups are tracked in [issues](https://github.com/hyunolike/hanjeok-agent/issues).

## 📄 License

[MIT](LICENSE) — © 2026 hyunolike.
