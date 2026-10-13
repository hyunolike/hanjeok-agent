"""Stage a verified local image context; no upload, download or cloud operation."""
import argparse,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'retrieval-service'),str(ROOT/'experiments/retrieval')]
from retrieval_service.index import load_index
from retrieval_service.lifecycle import publish
p=argparse.ArgumentParser();p.add_argument('--index',required=True);p.add_argument('--version',required=True);p.add_argument('--destination',required=True);p.add_argument('--model');a=p.parse_args()
index=load_index(a.index,a.version,a.model);dest=Path(a.destination)
if dest.exists():raise ValueError('destination already exists')
if index.vector.backend=='semantic' and index.vector.model is None:raise ValueError('verified local model required')
# Validation report has to pass the same explicit publication gates.
import tempfile
with tempfile.TemporaryDirectory() as tmp:publish(a.index,a.version,Path(tmp)/'registry.json')
dest.mkdir(parents=True)
try:
 shutil.copytree(a.index,dest/'index');(dest/'model').mkdir();(dest/'wheelhouse').mkdir()
 if a.model:shutil.copytree(a.model,dest/'model',dirs_exist_ok=True)
 for package,source in [('retrieval_service',ROOT/'retrieval-service/retrieval_service'),('retrieval_lab',ROOT/'experiments/retrieval/retrieval_lab')]:
  shutil.copytree(source,dest/package,ignore=shutil.ignore_patterns('__pycache__'))
 for name in ['Dockerfile','requirements-runtime.txt','requirements-semantic.txt']:shutil.copy2(Path(__file__).parent/name,dest/name)
 (dest/'.dockerignore').write_text('**/__pycache__\n**/*.pyc\n')
 print('Staged validated '+index.vector.backend+' context; operator wheelhouse and Linux build remain required.')
except BaseException:shutil.rmtree(dest);raise
