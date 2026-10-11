# Retrieval Bench

A local experiment asking when selecting passages from a linked corpus beats
putting all of it in the prompt. It does not change the Kotlin explanation
service or its deployment.

Phase 3 implements corpus loading/rebuilding, corpus-scoped vector similarity
search, one-hop graph expansion, and grounded question answering through HTTP
and CLI. Answers cite only documents supplied to the model. Invalid citations
get one repair attempt and then discard the entire answer.

Follow the [quickstart](../specs/001-retrieval-bench/quickstart.md) to run it.
The first graph load downloads a pinned local multilingual embedding model.
Answering needs an exported OpenAI key and uses a paid model. The default
pytest suite is offline; integration tests use local Neo4j and fake models.

Whole-corpus comparison and scoring are the next milestones. There are no
comparative quality results yet. Search currently performs exact cosine ranking
within a corpus, not approximate global ANN search; latency reports must name
that mode.

See the [Phase 3 smoke report](reports/phase3-smoke.md) for actual run evidence,
including the known retrieval miss and the remaining comparison scope.
