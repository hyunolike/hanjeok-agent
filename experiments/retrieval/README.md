# Local retrieval experiment

Production remains FULL. This module is outside production Kotlin wiring and packaged resources. It compares FULL, VECTOR and HYBRID_GRAPH with the preserved 29 fixtures plus 6 graph-boundary fixtures. Responses are scripted or capability-guard abstentions; no answer generation is performed.

## Run the tested environment

From the hanjeok-agent repository root, with the sibling travel-context-wiki checkout:

```bash
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv/bin/python -m unittest discover -s experiments/retrieval/tests -v
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv/bin/python -m retrieval_lab.run
JAVA_HOME=/Users/hyuno/Library/Java/JavaVirtualMachines/openjdk-21.0.2/Contents/Home GRADLE_USER_HOME=/Users/hyuno/Documents/Codex/2026-10-09/task-7/.gradle-home ./gradlew --offline --no-daemon -I experiments/retrieval/retrieval-citation.init.gradle test bootJar offlineContextEval --args=/tmp/hanjeok-retrieval-baseline.json retrievalCitationCheck
```

For another checkout, pass --agent-root and --wiki-root to the runner. The unittest suite locates the same sibling wiki. Reproduce into a separate directory with --output-dir /tmp/hanjeok-retrieval-repro and compare results.json, dataset.jsonl and graph-snapshot.json byte for byte. The default runner blocks socket connections and disables RAGAS telemetry. The explicit Neo4j backend permits only 127.0.0.1:17687. It never creates default LLM/embedding clients.

Python 3.12.9, scikit-learn 1.7.2, Neo4j driver 5.26.0 and RAGAS 0.3.9 were actually executed. requirements.in contains direct pins and requirements.lock freezes all 108 installed package versions; it is not a package artifact hash lock. The baseline 108-package freeze and .venv remain unchanged. The semantic extension below uses a separately installed environment. For a fresh, separately authorized environment, create a Python 3.12 venv and install requirements.lock. The existing venv is ignored by Git.

## What is implemented

- Corpus checks pinned body/sidecar, nine-document order, document and claim hashes, current wiki bytes and each source's bytes at its declared Git revision. Five source identities are verified. This verifies integrity; unverified/needs-review claims retain their status. The unsourced prompt is retained as mandatory policy but excluded from separate retrieval evidence. Eight documents are search eligible.
- VECTOR uses real sparse character TF-IDF vectors (char_wb, 2..4 character ngrams, L2 normalization, cosine dot product, top-k 3 and stable corpus-order ties). This is lexical retrieval, not a neural or multilingual semantic embedding. Many Korean questions do not match the English policy text; the empty candidates are reported.
- HYBRID_GRAPH executes a bounded in-process graph traversal over 15 nodes and 22 declared edges. Document/source edges come only from verified sidecar identities. Document/place and place/region edges come only from the seed's id/name/regionId. The region node has its declared ID, no imported regional descriptions. The seed is fixture-derived, not verified live tourism data. Synthetic, unsupported and undeclared edges are excluded. No transport or weather relationships are created.
- Neo4jGraph is a driver adapter with one fixed parameterized MATCH query, corpus namespace, node/edge whitelist, 2-hop bound, 9-document cap, 2-second managed transaction timeout and response document/source hash checks. Mock driver tests cover the request/response contract. READ_ACCESS is routing, not an ACL. The opt-in localhost-only loader and live-check helper executed against Community 5.26.31. Fifteen singleton traversals, two-hop region retrieval, synthetic isolation and real document/source hash tamper rejections passed. Mock contracts remain a separate category. The managed transaction uses unit_of_work(timeout=2), because the real 5.26 driver rejects a Query object passed to tx.run.
- All eight policies stay in system input; optional retrieved content goes into a labelled untrusted user-evidence block. FULL and conservative fallbacks preserve the original bundle bytes. History assistant answers never enter retrieval. A deterministic capability gate abstains on unsupported weather/hours/transport or rule override; it does not demonstrate model adherence.
- A harness-only Kotlin bridge applies the actual production CitationValidator to all 105 exported contexts, without changing production classes. Unknown/empty and omitted-seed probes are rejected. Its bounded topic checks establish citation boundaries, not semantic entailment.

This is direct relationship retrieval, not Microsoft's full community detection/summarization GraphRAG pipeline. Production has no runtime vector or Neo4j retrieval.

## Preserved TF-IDF baseline results

RAGAS 0.3.9 SingleTurnSample, EvaluationDataset and the public IDBasedContextPrecision/Recall.single_turn_ascore APIs were executed. These metrics use document-ID sets, not rank quality or an LLM judge. results/dataset.jsonl contains 210 native sample rows (candidate evidence and final context separately) and results/results.json contains 105 arm rows, 210 metric pairs and provenance.

The table uses the 24 rows per arm where the guard allowed a retrieval attempt. Six other rows conservatively retain FULL and five abstain (four unsupported-topic cases plus one rule override); aggregates preserve these strata. Undefined empty-set precision/recall is null, never replaced by a fabricated score. Precision means use only defined rows, so denominators differ.

| Arm | Candidate precision (defined rows) | Candidate recall (defined rows) | Final-context recall |
| --- | --- | --- | --- |
| FULL | 0.166667 (24/24) | 1.000000 (24/24) | 1.000000 (35/35) |
| VECTOR | 0.431373 (17/24) | 0.395833 (24/24) | 1.000000 (35/35) |
| HYBRID_GRAPH | 0.227941 (17/24) | 0.708333 (24/24) | 1.000000 (35/35) |

Policy retention, fixture-defined context coverage and determinism are 105/105. Graph expansion improves the candidate recall in this small oracle suite while adding unrelated documents and lowering precision. Final recall of 1.0 is largely guaranteed by the eight mandatory policies; it is not response correctness. The oracle is the preserved fixture's requiredEvidencePaths, not an independently labelled quality dataset.

The original context-byte ceiling remains 501/24,703 = 2.028% (about 2.03%). Results separately record original selected context bytes, system bytes, evidence wrapper bytes and assembled input bytes: moving the optional seed into a user block is not free. This tiny nine-document corpus with one optional seed cannot establish general token, latency, cost or accuracy gains.

## Local semantic extension, 2026-10-10

Actual CPU SentenceTransformer inference ran over the same 35 cases/three arms with the in-process graph. The model is sentence-transformers/distiluse-base-multilingual-cased-v1, pinned revision `826fee3d516ebb14987355af373f5b69101c7006`, Apache-2.0, 512 dimensions. Thirteen cached artifacts (543,484,070 bytes) were copied locally and every SHA-256 verified; there was no model download. `.venv-semantic` separately installs sentence-transformers 6.1.0, transformers 5.19.0 and torch 2.14.1 from official PyPI, alongside the original RAGAS/scikit/driver versions. requirements-semantic.lock freezes 114 installed packages; it is a version freeze, not a wheel hash lock.

Only safetensors weights and built-in Transformer/Pooling/Dense modules are allowed. `trust_remote_code=False`, `local_files_only=True`, offline HF settings and blocked runner sockets prohibit remote model code/requests. CPU uses one Torch thread and deterministic algorithms. Whole documents are tokenized without truncation, split into 41 windows of at most 128 tokens including special tokens, with 14-token overlap and adjusted boundaries after decoding/retokenizing. Each document is the L2-normalized mean of its normalized chunk vectors. Queries exceeding the window fail closed. Stable corpus order breaks equal-score ties. Artifact inventory, per-document chunk counts, matrix SHA-256 and execution settings are in each result's provenance.

On the same 24 retrieval-attempt rows, actual RAGAS ID candidate metrics are:

| Semantic arm | Precision (defined rows) | Recall (defined rows) | Complete final fixture coverage |
| --- | --- | --- | --- |
| FULL | 0.166667 (24/24) | 1.000000 (24/24) | 35/35 |
| VECTOR | 0.250000 (24/24) | 0.645833 (24/24) | 30/35 |
| HYBRID_GRAPH, in-process | 0.172619 (24/24) | 1.000000 (24/24) | 35/35 |

Five semantic VECTOR rows miss the optional seed, including the explicit-seed question. The runner records these coverage failures; it does not use expected fixture IDs to change retrieval or suppress failures. All eight policies and repeated/history-poisoned determinism pass 105/105. Final-context coverage is partly enforced by mandatory policies. The semantic result is not evidence that standalone VECTOR is ready for production. Comparing precision also requires the denominators: lexical baseline has seven empty candidate rows, semantic has none.

The real Kotlin CitationValidator matched all 105 semantic rows, rejected 210 empty/unknown probes and 25 omitted-seed probes. Citation-valid scripted rows are 34/35 FULL, 27/35 VECTOR and 32/35 HYBRID; invalid examples are intentionally retained, including two omitted-seed boundary fixtures and the empty-citation unknown-entity case. Contract agreement is not 105 successful answer citations. No generation or judge ran.

Run from the repository root:

```bash
# Existing local cache; aborts if any pinned artifact differs.
experiments/retrieval/.venv-semantic/bin/python experiments/retrieval/scripts/prepare-model.py
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv-semantic/bin/python -m unittest discover -s experiments/retrieval/tests -v
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv-semantic/bin/python -m retrieval_lab.run --enable-semantic --semantic-model experiments/retrieval/models/distiluse-base-multilingual-cased-v1 --output-dir experiments/retrieval/results/semantic-in-process
JAVA_HOME=/Users/hyuno/Library/Java/JavaVirtualMachines/openjdk-21.0.2/Contents/Home GRADLE_USER_HOME=/Users/hyuno/Documents/Codex/2026-10-09/task-7/.gradle-home ./gradlew --offline --no-daemon -I experiments/retrieval/retrieval-citation.init.gradle -PretrievalResults=experiments/retrieval/results/semantic-in-process/results.json -PretrievalCitationOutput=experiments/retrieval/results/semantic-in-process/citation-validation.json retrievalCitationCheck
```

For a fresh separately authorized setup: `python3.12 -m venv experiments/retrieval/.venv-semantic`, then that interpreter's `pip install --only-binary=:all: -r experiments/retrieval/requirements-semantic.lock`. Model preparation accepts `--snapshot PATH` and verifies the committed manifest; it never downloads. Model files and both venvs are Git-ignored. A second process reproduced results.json, dataset.jsonl, graph-snapshot.json and the embedding matrix hash byte for byte.

## Actual isolated Neo4j integration, 2026-10-10

The cached Community image runs Neo4j 5.26.31, verified through actual driver dbms.components(), with driver 5.26.0. Digest: `neo4j@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93`. No pull/download was needed. Only localhost Bolt 127.0.0.1:17687 is published; HTTP and usage reporting are disabled, with 2 GiB/2 CPU limits and own anonymous volumes. No existing bench-neo4j or operational containers/data are changed.

On this Docker Desktop, an internal network retained the requested port binding but exposed no actual port (`NetworkSettings.Ports={}`); the internal cypher-shell query succeeded while the host driver got connection refused. The helper therefore uses a dedicated bridge with `com.docker.network.bridge.enable_ip_masquerade=false`, whose actual loopback port publication was verified. The runner permits only that loopback address, and the driver disables telemetry. Disabling masquerading is a network configuration, not a claim of a general firewall ACL. The start/stop helper was actually executed and removes only ownership-labelled experiment resources.

The curated namespace has 15 nodes/22 edges. Actual fixed-read queries from every one of the 15 singleton starts match the in-process graph. A region start reaches exactly the seed document through two hops; longer source-neighbour paths do not enter that result. A synthetic transport edge to a fake document in a separate test namespace is ignored. Temporarily changing the actual Neo4j document SHA-256 or source signatures makes the adapter reject the response; both fields are restored. No synthetic relationship is promoted as a travel fact. All checks are in [actual integration report](results/neo4j-integration.json), separate from the two mock driver contract tests. Foreign-database loader refusal remains tested with a mock, not by touching an unrelated database. READ_ACCESS is routing, not an ACL.

Actual Neo4j TF-IDF and semantic comparisons each ran all 35 fixtures/three arms (105 rows, 210 native RAGAS samples). Row selections, sample bytes and ID scores exactly match the corresponding preserved in-process runs. On the 24 retrieval-attempt rows:

| Vector backend / arm | Candidate precision (defined) | Candidate recall (defined) | Complete final fixture coverage |
| --- | --- | --- | --- |
| TF-IDF / VECTOR | 0.431373 (17/24) | 0.395833 (24/24) | 35/35 |
| TF-IDF / HYBRID_GRAPH, Neo4j | 0.227941 (17/24) | 0.708333 (24/24) | 35/35 |
| Semantic / VECTOR | 0.250000 (24/24) | 0.645833 (24/24) | 30/35 |
| Semantic / HYBRID_GRAPH, Neo4j | 0.172619 (24/24) | 1.000000 (24/24) | 35/35 |

FULL candidate precision/recall is 0.166667/1.000000 (24 defined rows), complete final coverage 35/35. Six FULL fallbacks and five abstentions stay separate. All eight policies/determinism pass all 210 primary Neo4j arm rows. The five semantic VECTOR omissions are unchanged and are not repaired with oracle IDs. These are fixture ID metrics, not generated answer quality or Microsoft community summarization GraphRAG.

The real production CitationValidator matched 105/105 contracts in each Neo4j run, rejecting 210 empty/unknown probes per run and 29/25 omitted-seed probes respectively. Invalid scripted citations stay present. Each mode was rerun in a separate process: results.json, dataset.jsonl and graph-snapshot.json are byte-identical, with the same semantic matrix hash. See [TF-IDF results](results/neo4j-tfidf/results.json), [semantic results](results/neo4j-semantic/results.json) and [Neo4j validation](results/neo4j-validation.json). The owned container, anonymous volumes and network are removed after validation.

Reproduce from the repository root, using the already-cached image/model and environments:

```bash
experiments/retrieval/scripts/neo4j-local.sh start
# Wait for Started/Bolt ready in: experiments/retrieval/scripts/neo4j-local.sh status
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv/bin/python -m retrieval_lab.live --load --output experiments/retrieval/results/neo4j-integration.json
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv/bin/python -m retrieval_lab.run --graph-backend neo4j --output-dir experiments/retrieval/results/neo4j-tfidf
PYTHONPATH=experiments/retrieval PYTHONDONTWRITEBYTECODE=1 experiments/retrieval/.venv-semantic/bin/python -m retrieval_lab.run --graph-backend neo4j --enable-semantic --semantic-model experiments/retrieval/models/distiluse-base-multilingual-cased-v1 --output-dir experiments/retrieval/results/neo4j-semantic
experiments/retrieval/scripts/neo4j-local.sh stop
```

For Kotlin citation verification, use the earlier Gradle command with `-PretrievalResults=experiments/retrieval/results/neo4j-semantic/results.json` and `-PretrievalCitationOutput=experiments/retrieval/results/neo4j-semantic/citation-validation.json` (or replace semantic with tfidf). For byte reproduction, choose another --output-dir. All root baseline and semantic-in-process files remain unchanged.

## Executed and unexecuted

Executed baseline: Python 29 tests, 35 x 3 TF-IDF comparisons, actual RAGAS ID metrics, in-process verified graph, mock Neo4j contract, real Kotlin citation bridge, existing 325 server tests/bootJar/29-fixture baseline and wiki smoke/index checks. The historical results/validation.json describes that first phase; its unexecuted flags remain preserved.

Executed extension: 34 Python tests in both isolated environments, 105 actual semantic arm runs and 210 RAGAS samples, repeated-process byte reproduction, actual Kotlin citation contracts. See [extension validation](results/extension-validation.json) and [semantic results](results/semantic-in-process/results.json), [dataset](results/semantic-in-process/dataset.jsonl), [model manifest](results/semantic-model-manifest.json).

Executed Neo4j extension: actual Community server/loader/driver traversals and negative checks, 210 primary arm rows/420 RAGAS samples, equal in-process selections, two byte-identical independent reruns, 210 real citation contracts. The earlier automatic review blocker was cleared by the explicit follow-up authorization; historical extension-validation.json retains that earlier status. Current status is results/neo4j-validation.json.

Still unexecuted: answer generation, faithfulness/relevancy judging, paid APIs, external corpus upload, remote push/PR/merge/new deployment and the separate Hanjeok DB/SMTP rollout. Production remains FULL; operational and English experiment diagrams are installed; Korean-labelled replacements and the overall architecture image await receipt.

judge_scores is opt-in and requires caller-supplied real RAGAS LLM/embedding adapters; it constructs no client and is never called by the runner. faithfulness and responseRelevancy stay null / not_executed. No mock or deterministic gate score is represented as LLM judging.

## Sources and artifacts

- [scikit-learn TF-IDF documentation](https://scikit-learn.org/1.7/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
- [RAGAS ID precision](https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/context_precision/) and [ID recall](https://docs.ragas.io/en/v0.3.9/concepts/metrics/available_metrics/context_recall/) (also inspected in the installed 0.3.9 package)
- [Neo4j driver transactions](https://neo4j.com/docs/python-manual/current/transactions/)
- [Results](results/results.json), [dataset](results/dataset.jsonl), [declared graph](results/graph-snapshot.json), [production citation checks](results/citation-validation.json), [validation](results/validation.json)

Docker network reference: [bridge driver options](https://docs.docker.com/engine/network/drivers/bridge/) explain the masquerading option.
