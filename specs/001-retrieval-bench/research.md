# Phase 0 Research: Retrieval Bench

Resolves the unknowns the specification deferred, and records the decisions that
shape `plan.md`. Each entry states what was chosen, why, and what was rejected.

## 1. How the corpus grows for the crossover

**Decision**: Sample the work-log vault at increasing sizes — 25, 50, 100, 200,
340 documents — and treat the curated wiki (17 canonical pages) as a separate,
smaller point that is not on that curve. No duplication.

**Rationale**: The specification left this open and warned that duplication
threatens validity. It does: duplicated documents make retrieval look better
than it is, because a near-duplicate of the right answer is always available,
and they make whole-corpus prompting look worse than it is, because the prompt
fills with redundancy that a real corpus would not contain. Sampling avoids both
— every document at every size is a real document someone wrote.

The wiki cannot join the curve because its documents differ in kind, not just
count: typed, densely linked, with recorded evidence. Mixing it into the vault
series would vary shape and size together, and Principle II's logic applies to
corpus construction as much as to prompts — vary one thing.

So the report carries a curve (vault, five sizes) and a point (wiki). The curve
answers "where does the crossing happen"; the point answers "what happens when
links are dense and the corpus is tiny".

**Alternatives rejected**:
- *Duplicate documents with marked provenance*: cheapest, and the spec allowed
  it as a fallback. Rejected because it biases both arms in opposite directions,
  which is the worst case — the crossing point would move for reasons that have
  nothing to do with corpus size.
- *Include the wiki's non-canonical material (`raw/`, `records/`)*: grows the
  wiki to ~72 documents with real text. Rejected as the primary method because
  `raw/` files are source snapshots, not citable pages; admitting them changes
  what a citation means midway through the curve. Kept as a possible second
  point if the vault curve proves too coarse.

## 2. Graph store and vector index

**Decision**: Neo4j in Docker, using its native vector index for passage
embeddings. One store holds both the graph and the vectors.

**Rationale**: Native vector indexes have been part of Neo4j since 5.11, so the
retrieval arm can do "nearest passages, then walk the graph from their
documents" in one place. A separate vector store would mean two systems to keep
in sync, and Principle "the graph store is disposable" gets harder to honour the
moment derived state lives in two places that can disagree.

**Honest note on fit**: For 17 canonical pages, a graph database is
disproportionate — an in-memory dict would answer the same queries. It is
proportionate at 340 documents, and the subproject's stated purpose includes
exercising this technology. The disproportion at the small end is recorded here
rather than hidden, and it is itself part of the finding: if the graph arm loses
at 17 documents, "we used a database where a dictionary would do" is part of why.

**Alternatives rejected**:
- *NetworkX in memory*: simpler, no container, fast enough at these sizes.
  Rejected because it answers no question about operating a graph store, which
  is part of why this subproject exists.
- *Vector store beside a graph library*: two derived stores, two rebuild paths.

## 3. Embeddings

**Decision**: A local multilingual sentence-embedding model, run on the machine,
pinned by name and revision. Unit tests use a deterministic fake embedder and
never load the real model.

**Rationale**: The corpora are in two languages — the wiki is largely English,
the work-log vault is Korean — so a monolingual model would score one corpus
unfairly and the crossover would be measuring language, not size. Running
locally keeps embedding cost out of the per-run cost comparison, which matters
because that comparison is the point: if embeddings were billed per call, the
retrieval arm's cost would depend on a vendor's price list rather than on the
corpus.

Pinning name *and* revision matters for SC-007: rebuilding derived state must
reproduce the same retrieval results, and an unpinned model silently changes
under you.

**Alternatives rejected**:
- *Hosted embedding API*: no model download, better quality. Rejected because it
  puts a network call and an API key in the graph build, which the constitution
  forbids in unit tests and which makes the cost comparison depend on pricing.

## 4. Which RAGAS metrics apply to which arm

**Decision**: Score both arms with faithfulness and answer relevancy. Score
context precision and context recall for the retrieval arm only, and mark them
not applicable for whole-corpus prompting.

**Rationale**: Faithfulness checks the answer's claims against whatever context
was supplied, so it is defined for both arms and is the metric the comparison
turns on. Context precision measures whether relevant passages were ranked above
irrelevant ones in what was retrieved. The whole-corpus arm retrieves nothing —
it supplies everything — so its context precision would be, by construction,
roughly the fraction of the corpus that happens to be relevant. That number
falls as the corpus grows for reasons that have nothing to do with the arm's
quality, and reporting it as a score would make whole-corpus prompting look like
it degrades when it has not changed at all.

This is exactly the case FR-011 was written for, and it is the one a reader is
most likely to get wrong, so the report says "not applicable" in that cell
rather than leaving it blank.

**Alternatives rejected**:
- *Score context precision for both and note the caveat in prose*: a number in a
  table outlives the prose beside it.

## 5. Orchestration

**Decision**: A LangGraph state graph with nodes for retrieve, answer, validate
citations and repair, using conditional edges to route validation failures to
repair and back, with a budget carried in the state. Checkpointing enabled so a
run can be resumed and inspected.

**Rationale**: The shape is already known to work — the Kotlin service in this
repository runs the same loop by hand, with a round budget, a deadline and a
single repair. Rebuilding it as an explicit graph makes the comparison between
"hand-written loop" and "framework" available for free, since both exist in one
repository over the same rules.

The conditional edge is doing real work here and not decoration: citation
validation is a genuine branch whose target depends on runtime state, and the
repair path must be able to return to validation exactly once. A straight-line
chain cannot express that without a hand-rolled loop, which is what the other
implementation already is.

**Note**: `add_edge` for conditional routing is deprecated; use
`add_conditional_edges(source, router, {label: node})`, which maps a router's
return value to a node name explicitly.

**Alternatives rejected**:
- *A plain Python loop*: fewer moving parts, and honestly sufficient. Rejected
  because the subproject exists partly to exercise this framework, and because
  the comparison above is worth having.

## 6. Where LangChain is actually used

**Decision**: Use LangChain for the chat-model and embedding interfaces and for
the Neo4j vector integration. Write the corpus loaders directly — no document
loader from the library.

**Rationale**: Naming a dependency that does nothing is worse than omitting it,
because it suggests a familiarity the code does not demonstrate. The loaders
must read corpus-specific frontmatter and emit the shape Principle III requires;
a generic markdown loader would be wrapped so thickly that nothing of it would
remain. The model and vector interfaces are genuine reuse.

## 7. Chunking

**Decision**: Split canonical documents at markdown headings, keeping each
chunk's heading path, and never merge across documents. A document shorter than
the target size stays whole.

**Rationale**: A citation names a document, and a score must be able to point at
the passage that supported a claim. Heading sections are the smallest unit that
is still self-describing — a fixed-size window cuts mid-sentence and produces
passages that cannot be quoted back to a reader. Never merging across documents
keeps the passage-to-document mapping total, which FR-004 and the scoring both
depend on.

## Open Items Carried Into Planning

None. Every deferral the specification listed is resolved above. The
`contradictions`-as-attribute decision and the two-corpus decision were settled
in the specification's Assumptions and are not revisited here.
