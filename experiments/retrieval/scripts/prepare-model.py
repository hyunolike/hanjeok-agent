"""Copy the pinned existing cache snapshot; never download or execute model code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'results/semantic-model-manifest.json').read_text())
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot',type=Path,default=Path.home()/'.cache/huggingface/hub/models--sentence-transformers--distiluse-base-multilingual-cased-v1/snapshots'/manifest['revision'])
args=parser.parse_args()
source=args.snapshot.resolve()
target=root/'models/distiluse-base-multilingual-cased-v1'
# Validate the entire pinned inventory before writing any artifact.
for name,expected in manifest['files'].items():
    actual=hashlib.sha256((source/name).read_bytes()).hexdigest()
    if actual!=expected: raise ValueError('pinned artifact hash mismatch: '+name)
for name,expected in manifest['files'].items():
    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source/name,dest)
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==expected
(target/'retrieval-model-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Pinned local snapshot ready:',manifest['revision'],len(manifest['files']),'artifacts')
