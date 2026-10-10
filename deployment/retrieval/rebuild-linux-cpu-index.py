"""Offline Mac torch 2.14.1 -> Linux torch 2.14.1+cpu candidate; never relabel an index."""
import argparse,json,shutil
from pathlib import Path
from retrieval_service.index import FrozenCorpus,MODEL_REVISION,encoded,load_index,runtime_versions,strict_json
from retrieval_service.lifecycle import validate_candidate
from retrieval_lab.corpus import digest,require
from retrieval_lab.vector import LocalSemanticVector
import numpy as np

def verify_input(root,expected,current):
 root=Path(root)
 require(root.is_dir() and not root.is_symlink() and all(not p.is_symlink() for p in root.rglob('*')),'unsafe input symlink')
 manifest=strict_json((root/'manifest.json').read_bytes());version=manifest.pop('indexVersion')
 require(version==expected and digest(encoded(manifest))==version,'input identity drift')
 actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name not in ('manifest.json','validation.json')}
 require(actual==set(manifest['files']),'input inventory drift')
 for name,sha in manifest['files'].items():require(digest((root/name).read_bytes())==sha,'input artifact hash drift')
 require(manifest['vector']['backend']=='semantic' and manifest['vector']['modelRevision']==MODEL_REVISION,'fixed semantic model required')
 old=manifest['runtimeVersions'];require(old.get('torch')=='2.14.1' and current==dict(old,torch='2.14.1+cpu'),'only the exact Linux CPU torch variant may change')
 return manifest

def verify_model(root,model):
 model=Path(model)
 require(model.is_dir() and not model.is_symlink() and all(not p.is_symlink() for p in model.rglob('*')),'unsafe model symlink')
 expected=strict_json((Path(root)/'model.json').read_bytes())
 supplied=strict_json((model/'retrieval-model-manifest.json').read_bytes())
 require(all(supplied.get(k)==expected.get(k) for k in ('modelId','revision','files')),'model source pin drift')
 files={p.relative_to(model).as_posix() for p in model.rglob('*') if p.is_file() and p.name!='retrieval-model-manifest.json'}
 require(files==set(expected['files']),'model artifact inventory drift')
 for name,sha in expected['files'].items():require(digest((model/name).read_bytes())==sha,'model artifact hash drift')

def copy_candidate(root,destination):
 # mkdir is exclusive. If another writer created the target, never delete it.
 destination=Path(destination);destination.mkdir(parents=True)
 try:shutil.copytree(root,destination,dirs_exist_ok=True)
 except BaseException:
  shutil.rmtree(destination);raise

def rebuild(root,destination,expected,model,fixtures):
 root=Path(root);destination=Path(destination)
 require(not destination.exists(),'destination already exists')
 require(root.resolve() not in destination.resolve().parents,'destination inside input forbidden')
 current=runtime_versions('semantic');manifest=verify_input(root,expected,current)
 # Exercise the unchanged strict runtime loader, which must reject the old Mac pin.
 try:load_index(root,expected)
 except ValueError as error:require('runtime package version drift' in str(error),'unexpected old candidate rejection')
 else:raise ValueError('old exact runtime pin unexpectedly accepted')
 verify_model(root,model)
 corpus=FrozenCorpus(root,manifest);vector=LocalSemanticVector(corpus,model,enabled=True)
 require(vector.provenance['revision']==MODEL_REVISION and vector.matrix.shape==(len(corpus.evidence_ids),512),'model/dimension drift')
 copy_candidate(root,destination)
 try:
  # Input stays immutable; only this newly created output copy is writable.
  for p in [destination,*destination.rglob('*')]:p.chmod(0o755 if p.is_dir() else 0o644)
  (destination/'validation.json').unlink(missing_ok=True)
  np.savez_compressed(destination/'vectors.npz',matrix=vector.matrix)
  (destination/'model.json').write_bytes(encoded(vector.provenance))
  manifest['runtimeVersions']=current
  manifest['files']={p.relative_to(destination).as_posix():digest(p.read_bytes()) for p in sorted(destination.rglob('*')) if p.is_file() and p.name not in ('manifest.json','validation.json')}
  version=digest(encoded(manifest));require(version!=expected,'new CPU candidate identity required')
  manifest['indexVersion']=version;(destination/'manifest.json').write_bytes(encoded(manifest))
  report=validate_candidate(destination,version,fixtures,model)
  require(report['passed'] and report['fixtureCount']==35 and len(report['rows'])==70,'fixture validation failed')
  return {'oldIndexVersion':expected,'indexVersion':version,'runtimeVersions':current,'fixedModelRevision':MODEL_REVISION,'dimension':512,'totalChunks':vector.provenance['totalChunks'],'fixtureCount':35,'validationRows':70,'graphValidation':'in_process_contract; actual Neo4j tested separately','oldRuntimePinRejected':True,'llmCalls':0,'runtimeAutomaticallyUpdated':False}
 except BaseException:
  if destination.exists():shutil.rmtree(destination)
  raise

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('input','destination','version','model','fixtures'):p.add_argument('--'+key,required=True)
 a=p.parse_args();print(json.dumps(rebuild(a.input,a.destination,a.version,a.model,a.fixtures),ensure_ascii=False))
if __name__=='__main__':main()
