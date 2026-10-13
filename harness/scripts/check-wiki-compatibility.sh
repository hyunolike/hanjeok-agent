#!/usr/bin/env bash
# Read-only producer/consumer compatibility check. Never updates packaged artifacts.
set -euo pipefail
[ "$#" -eq 2 ] || { echo 'usage: check-wiki-compatibility.sh <wiki-worktree> <report.json>' >&2; exit 2; }
agent_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
wiki_root="$(cd "$1" && pwd)"
report_file="$2"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
for run in 1 2; do
  (cd "$wiki_root" && ./scripts/build-bundle.sh hanjeok) > "$work_dir/body-$run.txt"
  (cd "$wiki_root" && python3 scripts/provenance.py metadata hanjeok) > "$work_dir/meta-$run.json"
done
cmp "$work_dir/body-1.txt" "$work_dir/body-2.txt"
cmp "$work_dir/meta-1.json" "$work_dir/meta-2.json"
cmp "$work_dir/body-1.txt" "$agent_root/server/src/main/resources/prompts/hanjeok-bundle.txt"
cmp "$work_dir/meta-1.json" "$agent_root/server/src/main/resources/prompts/hanjeok-bundle.meta.json"
python3 - "$wiki_root" "$agent_root" "$work_dir" "$report_file" <<'PY'
import hashlib,json,pathlib,subprocess,sys
wiki,agent,tmp=map(pathlib.Path,sys.argv[1:4]); target=pathlib.Path(sys.argv[4])
suite=json.loads((agent/'harness/fixtures/context-selection/suite.json').read_text())
package=json.loads((wiki/'packages/hanjeok/context-bundle.json').read_text())
paths=package['canonicalContext']+package['recordContext']+['packages/hanjeok/prompt.md']
assert len(paths)==len(set(paths))==9
assert set(paths)==set(suite['requiredPaths'])|{suite['optionalPath']}
# Mandatory canonical pages and grade values are policies. The seed is descriptive data only.
seed=json.loads((wiki/suite['optionalPath']).read_text())
assert (tmp/'body-1.txt').read_bytes().count(b'----- FILE: ')==9
for key,file in [('bundleSha256','body-1.txt'),('metadataSha256','meta-1.json')]:
 assert hashlib.sha256((tmp/file).read_bytes()).hexdigest()==suite[key], key
required=set(suite['requiredPaths'])
rules=json.loads((wiki/'packages/explanation-rules.json').read_text())['rules']
# Every bundled policy home remains mandatory; external harness/generic homes are not model docs.
for rule in rules:
 for home in rule['homes']:
  if home['path'] in paths: assert home['path'] in required, rule['id']
report={'wikiBaseline':'7fc19c0c4a034868866bcf5a920e3f82050830c7','agentBaseline':'ea47917fd6e031b0f2c6ae387249dabd690d2aed','inventoryOrder':paths,'mandatoryDocuments':8,'optionalDocuments':1,'bundleUtf8Bytes':(tmp/'body-1.txt').stat().st_size,'bundleSha256':suite['bundleSha256'],'metadataSha256':suite['metadataSha256'],'producerRunsByteIdentical':True,'producerConsumerBodyByteIdentical':True,'producerConsumerMetadataByteIdentical':True,'bundledRuleHomesRetained':True,'selectionClassificationVerified':True,'scope':'local read-only compatibility; no deploy or model call'}
target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('compatible: 9 docs, body and sidecar byte-identical; all bundled policy homes retained')
PY
