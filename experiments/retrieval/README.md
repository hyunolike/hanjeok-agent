# Local retrieval experiment

Production remains FULL. This module is outside production Kotlin wiring and packaged resources. It compares FULL, VECTOR and HYBRID_GRAPH with the preserved 29 fixtures plus 6 graph-boundary fixtures. Responses are scripted or capability-guard abstentions; no answer generation is performed.

## Run the tested environment

From the hanjeok-agent repository root, with the sibling travel-context-wiki checkout:

```bash
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv/bin/python -m unittest discover -s experiments/retrieval/tests -v
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv/bin/python -m retrieval_lab.run
JAVA_HOME=/Users/hyuno/Library/Java/JavaVirtualMachines/openjdk-21.0.2/Contents/Home GRADLE_USER_HOME=/Users/hyuno/Documents/Codex/2026-10-09/task-7/.gradle-home ./gradlew --offline --no-daemon -I experiments/retrieval/retrieval-citation.init.gradle test bootJar offlineContextEval --args=/tmp/hanjeok-retrieval-baseline.json retrievalCitationCheck
```

For another checkout, pass --agent-root and --wiki-root to the runner. The unittest suite locates the same sibling wiki. Reproduce into a separate directory with --output-dir /tmp/hanjeok-retrieval-repro and compare results.json, dataset.jsonl and graph-snapshot.json byte for byte. The runner blocks socket connections and disables RAGAS telemetry. It never creates default LLM/embedding clients.

Python 3.12.9, scikit-learn 1.7.2, Neo4j driver 5.26.0 and RAGAS 0.3.9 were actually executed. requirements.in contains direct pins and requirements.lock freezes all 108 installed package versions; it is not a package artifact hash lock. No installation or download was performed during this resumed implementation. For a fresh, separately authorized environment, create a Python 3.12 venv and install requirements.lock. The existing venv is ignored by Git.

## What is implemented

- Corpus checks pinned body/sidecar, nine-document order, document and claim hashes, current wiki bytes and each source's bytes at its declared Git revision. Five source identities are verified. This verifies integrity; unverified/needs-review claims retain their status. The unsourced prompt is retained as mandatory policy but excluded from separate retrieval evidence. Eight documents are search eligible.
- VECTOR uses real sparse character TF-IDF vectors (char_wb, 2..4 character ngrams, L2 normalization, cosine dot product, top-k 3 and stable corpus-order ties). This is lexical retrieval, not a neural or multilingual semantic embedding. Many Korean questions do not match the English policy text; the empty candidates are reported.
- HYBRID_GRAPH executes a bounded in-process graph traversal over 15 nodes and 22 declared edges. Document/source edges come only from verified sidecar identities. Document/place and place/region edges come only from the seed's id/name/regionId. The region node has its declared ID, no imported regional descriptions. The seed is fixture-derived, not verified live tourism data. Synthetic, unsupported and undeclared edges are excluded. No transport or weather relationships are created.
- Neo4jGraph is a driver adapter with one fixed parameterized MATCH query, corpus namespace, node/edge whitelist, 2-hop bound, 9-document cap, 2-second query timeout and response document/source hash checks. Mock driver tests cover the request/response contract. READ_ACCESS is routing, not an ACL. The exported graph describes the schema for later isolated loading; a Neo4j server, loader and Docker integration were not executed or delivered here. The query was not validated by a live Cypher parser.
- All eight policies stay in system input; optional retrieved content goes into a labelled untrusted user-evidence block. FULL and conservative fallbacks preserve the original bundle bytes. History assistant answers never enter retrieval. A deterministic capability gate abstains on unsupported weather/hours/transport or rule override; it does not demonstrate model adherence.
- A harness-only Kotlin bridge applies the actual production CitationValidator to all 105 exported contexts, without changing production classes. Unknown/empty and omitted-seed probes are rejected. Its bounded topic checks establish citation boundaries, not semantic entailment.

This is direct relationship retrieval, not Microsoft's full community detection/summarization GraphRAG pipeline. Production has no runtime vector or Neo4j retrieval.

## Measured results

RAGAS 0.3.9 SingleTurnSample, EvaluationDataset and the public IDBasedContextPrecision/Recall.single_turn_ascore APIs were executed. These metrics use document-ID sets, not rank quality or an LLM judge. results/dataset.jsonl contains 210 native sample rows (candidate evidence and final context separately) and results/results.json contains 105 arm rows, 210 metric pairs and provenance.

The table uses the 24 rows per arm where the guard allowed a retrieval attempt. Six other rows conservatively retain FULL and five abstain (four unsupported-topic cases plus one rule override); aggregates preserve these strata. Undefined empty-set precision/recall is null, never replaced by a fabricated score. Precision means use only defined rows, so denominators differ.

| Arm | Candidate precision (defined rows) | Candidate recall (defined rows) | Final-context recall |
| --- | --- | --- | --- |
| FULL | 0.166667 (24/24) | 1.000000 (24/24) | 1.000000 (35/35) |
| VECTOR | 0.431373 (17/24) | 0.395833 (24/24) | 1.000000 (35/35) |
| HYBRID_GRAPH | 0.227941 (17/24) | 0.708333 (24/24) | 1.000000 (35/35) |

Policy retention, fixture-defined context coverage and determinism are 105/105. Graph expansion improves the candidate recall in this small oracle suite while adding unrelated documents and lowering precision. Final recall of 1.0 is largely guaranteed by the eight mandatory policies; it is not response correctness. The oracle is the preserved fixture's requiredEvidencePaths, not an independently labelled quality dataset.

The original context-byte ceiling remains 501/24,703 = 2.028% (about 2.03%). Results separately record original selected context bytes, system bytes, evidence wrapper bytes and assembled input bytes: moving the optional seed into a user block is not free. This tiny nine-document corpus with one optional seed cannot establish general token, latency, cost or accuracy gains.

## Executed and unexecuted

Executed: Python 29 tests, 35 x 3 comparisons, actual RAGAS ID metrics, in-process verified graph, mock Neo4j contract, actual Kotlin citation bridge, existing server tests/bootJar/29-fixture baseline and wiki smoke/index checks. See results/validation.json for exact counts and reproducibility evidence.

Not executed: Neo4j server/container integration, semantic embedding inference, answer generation, faithfulness/relevancy judging, paid calls, external data upload, push/PR/merge/deployment, or the separate Hanjeok DB/SMTP rollout. Existing README image slots remain unfilled.

LocalSemanticVector is an opt-in adapter requiring already-local SentenceTransformer weights, a manifest with a pinned 40-character revision and every artifact SHA-256, local_files_only and CPU execution. SentenceTransformers is not installed in the tested freeze and no model was downloaded or executed. Its result must be labelled separately if run later.

judge_scores is opt-in and requires caller-supplied real RAGAS LLM/embedding adapters; it constructs no client and is never called by the runner. faithfulness and responseRelevancy stay null / not_executed. No mock or deterministic gate score is represented as LLM judging.

## Sources and artifacts

- [scikit-learn TF-IDF documentation](https://scikit-learn.org/1.7/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
- [RAGAS ID precision](https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/context_precision/) and [ID recall](https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/context_recall/) (also inspected in the installed 0.3.9 package)
- [Neo4j driver transactions](https://neo4j.com/docs/python-manual/current/transactions/)
- [Results](results/results.json), [dataset](results/dataset.jsonl), [declared graph](results/graph-snapshot.json), [production citation checks](results/citation-validation.json), [validation](results/validation.json)
