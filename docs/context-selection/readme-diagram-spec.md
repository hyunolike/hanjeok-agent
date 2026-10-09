# README diagram specification (2026-10-09)

No new raster image has been generated or installed. Parent will create the approved soft-3D images. Keep labels short, arrows explicit and the build/runtime boundary visible. Decorative icons may be cute; no decoration may imply the LLM chooses a route or sidecar enters a prompt.

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
