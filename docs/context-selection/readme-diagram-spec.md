> Historical specification. The Mermaid replacement recorded on 2026-10-10 was superseded by the user’s later correction: restore useful existing 3D overview/input/request/lab figures and remove redundant diagrams, hand-drawn statistics and decorative stack embeds. Current README structure is recorded in readme-illustration-correction.json; no new generated image was added.

# README diagram specification (2026-10-09)

Operational raster diagrams A/B were received and visually reviewed on 2026-10-10; the applicable images are installed below. English experiment diagram C is installed; Korean B/C and English/Korean overall architecture diagrams are installed. Korean A is installed and visually reviewed. Keep labels short, arrows explicit and the build/runtime boundary visible. Decorative icons may be cute; no decoration may imply the LLM chooses a route or sidecar enters a prompt.

## Review of existing pictures and prose

Agent README.md / README.ko.md currently embed docs/images/flow.en.svg / flow.svg and deploy.en.svg / deploy.svg under “The system, twice” / “시스템을 두 번 그립니다”. The SVG source and generators put ForbiddenBehaviours/ViolationTally in the request picture, although those are evaluation-only. The deployed EXPLAIN cache and blocking ASK lane are missing. Deployment labels imply three backend and one LLM call per request; EXPLAIN cache hits skip the model, and streaming ASK may have multiple calls. Existing media/screens are historical fixtures or earlier experiments, not current production LLM verification.

Wiki README.md / README.ko.md / README.ja.md use Mermaid under Architecture, Service Integration Model, Knowledge Store Boundary and Agent Delivery. The general service integration sequence suggests runtime document retrieval and weather context. For the deployed Hanjeok integration, context is built into the image, all nine documents enter the system prompt, and no weather fact is supplied. Generic wiki capabilities must be labelled separately from this integration. The knowledge-store paragraph also contradicts the narrowly allowed scheduled public reference capture; correct the wording without broadening collection scope.

## Image A: shared two-input architecture (wiki primary picture; agent overview)

Suggested destination: wiki docs/images/hanjeok-two-inputs.png and agent docs/images/hanjeok-two-inputs.png.

Build zone, left: [Wiki manual: versioned policies + records] → [Build + source checks] → [Agent image: bundle.txt + metadata.json]. Label bundle “9 docs / 24,703 bytes”.

Runtime zone, right: [Agent image] → [BundleLoader: verify once] → [Static manual / system]. Branch metadata → [Server integrity + provenance] only. [Hanjeok Backend: route + current facts] → [Agent: fetch facts / user] → [LLM: explanation only]. [Static manual / system] → [LLM: explanation only] → [Citation gate] → [Browser]. Dashed boundary between build and runtime. Backend decides ranking/order. No metadata→LLM edge. No runtime GitHub lookup, retrieval engine, GraphRAG or vector DB.

Keep “server integrity” badge outside the two model inputs; explain that body and sidecar are packaged together. Current backend facts are query results, not a guarantee of source/forecast freshness. Optional inset [Offline SELECTED_EXPERIMENT] must be outside the deployment boundary, labelled “experiment only / FULL default”. It may be omitted from the picture if it makes the two inputs harder to read.

Insertion: wiki Agent Delivery → “Hanjeok build-time and runtime contract” (all 3 README languages), before the contract paragraphs. Agent replace the existing “Where it runs” image block, retaining a prose link to the detailed deployment guide.

## Image B: three request lanes (agent primary request picture)

Suggested destination: agent docs/images/request-paths.png (one image shared by both READMEs; English labels + localized captions).

Shared input strip: [Verified static manual / system] and [Fresh backend facts / user]. Browser calls the agent server, never provider/backend directly.

EXPLAIN: [Fetch facts] → [UUID + facts hash cache]. HIT → [Saved explanation + generatedAt] → [Browser]. MISS/EXPIRED → [LLM] → [CitationValidator] → [Save 5 min from completion] → [Browser]. Failed facts or generation → [Unavailable], with no stale fallback. In-flight same-key requests share generation. Facts retrieval always runs; 3 backend calls in the current facts source, then 0 model calls on a hit.

Blocking ASK: [Fetch facts + question/history] → [LLM] → [CitationValidator] → [Answer / Unavailable]. No EXPLAIN cache, no tools.

Streaming ASK: [Fetch facts + question/history] → [AgentLoop] ↔ [LLM]. LLM proposes [congestion / alternatives] → [Server argument check] → [Backend lookup] → [Tool result into loop]. Rejected calls return a rejected result and failed lookups return an unavailable result; both are excluded from the evidence union. [AgentLoop final text] → [AskStreamGate] → [citations → delta → done]. Invalid citation may repair once; zero delta before unavailable; aborted discards partial answer. Budget badge “2 tool rounds / 60s”. No EXPLAIN cache. History is context only and client-owned.

Insertion: replace agent current “What one request does” SVG block in both README languages. Move the historical drawing behind a clearly labelled source link until parent supplies the new image. Do not claim an image exists before the PNG is installed.

## Source anchors for renderer/reviewer

- Wiki scripts/build-bundle.sh + scripts/provenance.py: order, bytes, source checks, sidecar creation.
- Agent .github/workflows/build.yml, Dockerfile: build-time packaging and drift checks.
- BundleLoader.kt, BundleMetadata.kt, PromptAssembler.kt and HermesConfig.kt: server validation, full system input, singleton unchanged.
- FactsSource.kt / FactsProjection.kt: backend retrieval and facts projection.
- CourseExplainer.kt / ExplanationCache.kt: facts-first cache, exact facts hash, 5 minute TTL, coalescing.
- CourseQuestionService.kt: blocking/streaming paths, user text and history.
- AgentLoop.kt / CourseTools.kt / ToolFacts.kt / AskStreamGate.kt: bounded tools, result union and citation gate.
- ContextController.kt: sidecar provenance and document browser.

## Verified deployment caption

As recorded at 2026-10-09 09:13 UTC, agent ea47917 runs in Cloud Run revision hermes-agent-ea47917-b64ed4cc2, Ready, traffic 100%, health/readiness UP. The full bundle and sidecar hashes match the packaged artifacts. agent.hanjeok.com frontend deployment is complete. This deployment check made no actual LLM call. Earlier paid measurements do not verify this revised prompt/policy/cache deployment. Separate hyunolike/hanjeok database/SMTP rollout remains held.


## Installed operational images (2026-10-10)

A: docs/images/hanjeok-two-inputs.png, 1672×941, SHA-256 96adc5b88f0498ddb3831a6d4eae77dfaec223547e072fbe9215233cc83dd00c. It separates build and runtime, sends static manual and backend facts into the model, and keeps provenance server-only with production FULL.

B: agent docs/images/request-paths.png, 1672×941, SHA-256 ff4737e906208ae316bb083e052016370161cc8db4ab504032c6ee75b66c92f0. Pixel review distinguishes EXPLAIN cache hit/miss, blocking ASK without tools/cache, and streaming ASK whose tools are server-validated. Captions clarify TTL from generation completion, citation-gated body emission and 2 rounds/60 seconds. Earlier SVG links stay historical.

## Image C: local retrieval experiment (English image installed)

Title: Local Retrieval Lab — Experiment Only. Verified pinned corpus (9 docs; 8 mandatory policies, 8 source-backed search docs) → FULL / VECTOR / HYBRID_GRAPH. FULL keeps all 9 docs. VECTOR ranks top 3 with TF-IDF lexical vectors or the pinned multilingual CPU semantic model. HYBRID adds actual Neo4j 5.26.31 relationship retrieval, max 2 hops/9 documents. Relation inset: Document→Source (HAS_SOURCE), Document→Place (DESCRIBES), Place→Region (IN_REGION). Output union always retains eight policies; optional source-integrity-checked evidence remains untrusted. Then citation boundary checks and actual RAGAS 0.3.9 ID precision/recall for candidate and final-context IDs. Badges: Actual local Neo4j + embeddings; scripted responses; LLM answer generation/judge NOT RUN; Production FULL / no runtime retrieval. Optional note: semantic VECTOR misses seed in 5/35 cases. No weather/transport/synthetic fact edges or Microsoft community clustering/summaries. English C pixels were inspected before insertion. C: docs/images/local-retrieval-lab.png, 1672×941, SHA-256 2571b6eada9086a36c729111173403f26c67693a9e2bbe99fef8acb9d3408830. Version-specific and retrieval-quality limitations are retained in the caption. Korean C is also installed and visually reviewed.


## Overall architecture constraints

Collection is a restricted public-reference/raw evidence path. Raw snapshots do not automatically become canonical policy or operational input. Canonical pages and declared seed records are explicitly selected by packages/hanjeok/context-bundle.json; the service prompt is also bundled. This is not an all-reviewed gate: unverified/needs-review/contested context remains qualified policy context, never verified facts. Hash/revision integrity checks preserve review status and do not establish semantic truth. Build-time provenance checks produce deterministic bundle text and a separate sidecar, and CI compares both packaged artifacts. Runtime loader verifies both; only full bundle text enters system input, while sidecar provenance remains server-side. Browser calls the agent server, which obtains backend-ranked route/current facts and calls the LLM for explanation; citations gate output. Neo4j and RAGAS belong to the isolated offline lab over the pinned corpus, never to production runtime retrieval. Document/source edges come from the sidecar; place/region edges are declared seed data, not live backend, transport or weather facts. ID precision/recall has no LLM generation or judge step.


## Installed localized and overall images (2026-10-10)

- docs/images/request-paths-ko.png — 1672×941, SHA-256 d945073104bf363092e29356b355a27c4fc906270468d156bbc098e75d2e2335.
- docs/images/local-retrieval-lab-ko.png — 1672×941, SHA-256 cac28383f6e2d701fcbfce3410fe64e4a83e8746a9a2bfcea43c462fbbf621b4.
- docs/images/hanjeok-wiki-agent-overview.ko.png — 1672×941, SHA-256 db43e8ff0822978709ef354e8c350838f7c0110672c80fecd2d676f215e17c66.
- docs/images/hanjeok-wiki-agent-overview.en.png — 1672×941, SHA-256 3c74eec5737f4769705b8134a044dc1cdbbe83fd401b52bf7d4dd03e4ac47c8c.

Pixel review confirms the three request lanes, experiment-only ID evaluation, full production context and server-only provenance. Overall diagrams show public raw snapshots, PR review/canonical documentation and explicit package selection; captions clarify that the generator preserves review status rather than admitting only reviewed claims. Browser request lines/cache detail are deliberately omitted from the overview. English originals and historical SVGs are preserved. Korean READMEs use Korean-labelled PNGs; Korean A is installed and all applicable language-specific diagrams are complete.


Korean A: docs/images/hanjeok-two-inputs-ko.png, 1672×941, SHA-256 fcbe67723a4fa197d7beea315b455f23439e4277c2a1b98cc0b1aa5635f1205b. Pixel review confirms the two model inputs, server-only source metadata, backend ranking and full production wiki. Korean READMEs now use the Korean A image and enlargement link.
