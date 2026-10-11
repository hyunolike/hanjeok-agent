# Retrieval Bench

A local experiment asking when selecting passages from a linked corpus beats
putting all of it in the prompt. It does not change the Kotlin explanation
service or its deployment.

Phases 3–5 implement corpus loading/rebuilding, corpus-scoped vector similarity
search, one-hop graph expansion, and grounded question answering through HTTP
and CLI. Answers cite only documents supplied to the model. Invalid citations
get one repair attempt and then discard the entire answer.

Follow the [quickstart](../specs/001-retrieval-bench/quickstart.md) to run it.
The first graph load downloads a pinned local multilingual embedding model.
Answering and judging use NVIDIA NIM with an exported `NVIDIA_API_KEY`.
The default model for both is `nvidia/nemotron-3-super-120b-a12b`, reasoning off.
The OpenAI-compatible SDK is only a transport; requests go to NVIDIA, and no
OpenAI or other provider fallback exists. The default
pytest suite is offline; integration tests use local Neo4j and fake models.

Whole-corpus prompting and `bench pair --show-diff` now run through that same
pipeline and append both runs plus pair validity under `runs/`. `bench run`
evaluates stored question sets and saves RAGAS observations with sample counts,
outcomes and provenance. `bench report --id <uuid>` reads a saved report offline.
Search currently performs exact cosine ranking
within a corpus, not approximate global ANN search; latency reports must name
that mode.

See the [Phase 3 smoke report](reports/phase3-smoke.md) for actual run evidence,
including the known retrieval miss and the remaining comparison scope.

See the [Phase 4 pair smoke](reports/phase4-smoke.md) for actual paired inputs,
usage and the question where whole supplies evidence that graph misses.

The stored [wiki-v1 questions](questions/wiki-v1.yaml) contain 18 single-document,
7 multi-document and 5 unsupported questions. Phase 5 uses the full loaded
corpus; size sampling and crossover measurements remain Phase 6.

See the [Phase 5 NVIDIA evaluation](reports/phase5-evaluation.md) for both full
executions. The second lost samples to provider failures, so the original
repeatability target remains unverified; its partial means are not a pass.
