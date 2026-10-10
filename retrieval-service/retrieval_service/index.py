"""Immutable, hash-pinned JSON/NPZ index. Git verification only runs at build time."""
import json,re,shutil
from importlib.metadata import version as package_version
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from retrieval_lab.corpus import Corpus,Document,POLICIES,OPTIONAL,digest,require,safe_path
from retrieval_lab.graph import GraphSnapshot
from retrieval_lab.vector import LexicalVector,LocalSemanticVector

RUNTIME_PACKAGES=('numpy','scikit-learn','neo4j')
SEMANTIC_PACKAGES=('sentence-transformers','transformers','torch')

def runtime_versions(backend):
 return {p:package_version(p) for p in RUNTIME_PACKAGES+(SEMANTIC_PACKAGES if backend=='semantic' else ())}

MODEL_REVISION='826fee3d516ebb14987355af373f5b69101c7006'

def encoded(value):
 return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def strict_json(data):
 def pairs(items):
  d={}
  for k,v in items:
   require(k not in d,'duplicate JSON key');d[k]=v
  return d
 return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('non-finite JSON')))

def build_index(agent,wiki,destination,backend='tfidf',model_path=None):
 corpus=Corpus(agent,wiki);dest=Path(destination);require(not dest.exists(),'candidate already exists')
 require(backend in ('tfidf','semantic'),'unsupported vector backend')
 vector=LexicalVector(corpus) if backend=='tfidf' else LocalSemanticVector(corpus,model_path,enabled=True)
 if backend=='semantic':require(vector.provenance['revision']==MODEL_REVISION,'semantic revision mismatch')
 dest.mkdir(parents=True)
 try:
  (dest/'bundle.txt').write_bytes(corpus.raw.encode());(dest/'metadata.json').write_bytes((Path(agent)/'server/src/main/resources/prompts/hanjeok-bundle.meta.json').read_bytes())
  (dest/'sources').mkdir()
  for path,revision,sha in corpus.verified_sources:(dest/'sources'/f'{sha}.bin').write_bytes((Path(wiki)/path).read_bytes())
  corpus.namespace='retrieval-index:'+digest(digest(corpus.raw)+'@'+digest((dest/'metadata.json').read_bytes()))
  (dest/'graph.json').write_bytes(encoded(GraphSnapshot(corpus).export()))
  info={'backend':backend,'ids':list(vector.ids),'modelRevision':'tfidf-v1' if backend=='tfidf' else MODEL_REVISION}
  if backend=='tfidf':
   (dest/'vocabulary.json').write_bytes(encoded(vector.vectorizer.vocabulary_))
   np.savez_compressed(dest/'vectors.npz',matrix=vector.matrix.toarray(),idf=vector.vectorizer.idf_)
   info.update(algorithm='char_wb-2:4-tfidf-cosine',dtype='float64')
  else:
   np.savez_compressed(dest/'vectors.npz',matrix=vector.matrix)
   (dest/'model.json').write_bytes(encoded(vector.provenance))
   info.update(algorithm='normalized-mean-chunks-cosine',dtype='float32')
  files={p.relative_to(dest).as_posix():digest(p.read_bytes()) for p in sorted(dest.rglob('*')) if p.is_file()}
  manifest={'schemaVersion':1,'bundleSha256':digest(corpus.raw),'metadataSha256':digest((dest/'metadata.json').read_bytes()),'files':files,'vector':info,'runtimeVersions':runtime_versions(backend)}
  manifest['indexVersion']=digest(encoded(manifest));(dest/'manifest.json').write_bytes(encoded(manifest))
  load_index(dest,manifest['indexVersion'])
  return manifest['indexVersion']
 except BaseException:
  shutil.rmtree(dest);raise

class FrozenCorpus:
 def __init__(self,root,manifest):
  self.raw=(root/'bundle.txt').read_text();self.metadata=strict_json((root/'metadata.json').read_bytes())
  require(digest(self.raw)==manifest['bundleSha256'] and digest((root/'metadata.json').read_bytes())==manifest['metadataSha256'],'corpus identity mismatch')
  require(self.metadata['schemaVersion']==1 and self.metadata['bundleSha256']==digest(self.raw),'metadata mismatch')
  require(re.fullmatch('[0-9a-f]{64}',self.metadata['provenanceSha256']),'invalid provenance hash')
  self.namespace='retrieval-index:'+digest(manifest['bundleSha256']+'@'+manifest['metadataSha256'])
  markers=list(re.finditer(r'^----- FILE: (.+) -----$',self.raw,re.M));require(len(markers)==9 and markers[0].start()==0 and len(self.metadata['documents'])==9,'invalid corpus inventory')
  self.documents={};sources=set()
  for i,mark in enumerate(markers):
   end=markers[i+1].start() if i+1<len(markers) else len(self.raw);path=safe_path(mark[1]);original=self.raw[mark.end()+1:end].removesuffix('\n');entry=self.metadata['documents'][i]
   require(path not in self.documents and path==entry['path'] and digest(original)==entry['sha256'],'document drift')
   require('----- FILE:' not in original,'embedded marker')
   source_items=tuple((safe_path(s['path']),s['revision'],s['sha256']) for s in entry['sources'])
   for p,revision,sha in source_items:
    require(re.fullmatch('[0-9a-f]{40}',revision) and re.fullmatch('[0-9a-f]{64}',sha),'invalid source pin')
    require(digest((root/'sources'/f'{sha}.bin').read_bytes())==sha,'source bytes mismatch');sources.add((p,revision,sha))
   for c in entry['claims']:
    require(c['status'] in ('unverified','needs-review','reviewed') and c['sources']==entry['sources'],'claim state/source drift')
    text=c.get('quote') if c['scope']=='quote' else original
    require(isinstance(text,str) and text in original and digest(text)==c['sha256'],'claim drift')
   require(bool(entry['claims']),'missing claims')
   self.documents[path]=Document(path,original,self.raw[mark.start():end],entry['sha256'],source_items,tuple(c['status'] for c in entry['claims']))
  require(set(self.documents)==POLICIES|{OPTIONAL},'mandatory inventory mismatch')
  self.evidence_ids=tuple(p for p,d in self.documents.items() if d.sources);self.verified_sources=tuple(sorted(sources))

class FrozenVector:
 def __init__(self,root,manifest,corpus,model_path=None):
  self.ids=tuple(manifest['vector']['ids']);self.backend=manifest['vector']['backend']
  require(self.ids==corpus.evidence_ids,'vector inventory drift')
  with np.load(root/'vectors.npz',allow_pickle=False) as data:
   require(set(data.files)==({'matrix','idf'} if self.backend=='tfidf' else {'matrix'}),'unsafe array inventory')
   self.matrix=data['matrix'].copy();self.idf=data['idf'].copy() if self.backend=='tfidf' else None
  require(self.matrix.ndim==2 and self.matrix.shape[0]==len(self.ids) and 0<self.matrix.shape[1]<=100_000 and np.isfinite(self.matrix).all(),'invalid matrix')
  require(np.allclose(np.linalg.norm(self.matrix,axis=1),1,atol=1e-6),'unnormalized matrix')
  if self.backend=='tfidf':
   from sklearn.feature_extraction.text import TfidfVectorizer
   self.vocabulary=strict_json((root/'vocabulary.json').read_bytes());require(set(self.vocabulary.values())==set(range(self.matrix.shape[1])),'invalid vocabulary')
   require(self.idf.shape==(self.matrix.shape[1],) and np.isfinite(self.idf).all() and (self.idf>0).all(),'invalid idf')
   self.analyzer=TfidfVectorizer(analyzer='char_wb',ngram_range=(2,4),lowercase=True).build_analyzer()
  elif self.backend=='semantic':
   require(self.matrix.shape[1]==512 and manifest['vector']['modelRevision']==MODEL_REVISION,'semantic dimensions/revision mismatch')
   self.model=None
   if model_path:self.model=self._query_model(Path(model_path),strict_json((root/'model.json').read_bytes()))
  else:raise ValueError('unsupported backend')
 def _query_model(self,path,manifest):
  require(path.is_dir() and not path.is_symlink() and all(not p.is_symlink() for p in path.rglob('*')),'unsafe model directory')
  require(manifest['revision']==MODEL_REVISION,'invalid model revision')
  local=strict_json((path/'retrieval-model-manifest.json').read_bytes());require(local['revision']==manifest['revision'] and local['files']==manifest['files'],'model manifest mismatch')
  actual={p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file() and p.name!='retrieval-model-manifest.json'}
  require(actual==set(local['files']),'model inventory drift')
  for name,sha in local['files'].items():
   require(Path(name).suffix in ('.json','.txt','.md','.safetensors') and not (path/name).is_symlink(),'unsafe model artifact')
   require(digest((path/safe_path(name)).read_bytes())==sha,'model hash drift')
  require('auto_map' not in strict_json((path/'config.json').read_bytes()),'remote model code')
  require([m['type'] for m in strict_json((path/'modules.json').read_bytes())]==['sentence_transformers.models.Transformer','sentence_transformers.models.Pooling','sentence_transformers.models.Dense'],'unsafe model modules')
  import os,torch
  os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1');torch.set_num_threads(1);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
  from sentence_transformers import SentenceTransformer
  return SentenceTransformer(str(path),device='cpu',local_files_only=True,trust_remote_code=False)
 def search(self,query,top_k=3):
  require(type(top_k) is int and 1<=top_k<=3,'top_k cap')
  if self.backend=='tfidf':
   v=np.zeros(self.matrix.shape[1])
   for term in self.analyzer(query):
    index=self.vocabulary.get(term)
    if index is not None:v[index]+=1
   v*=self.idf;norm=np.linalg.norm(v);v=v/norm if norm else v
  else:
   require(self.model is not None,'semantic query model unavailable')
   require(len(self.model.tokenizer.encode(query))<=self.model.max_seq_length,'query token window exceeded')
   v=self.model.encode([query],normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)[0]
  scores=self.matrix@v;require(np.isfinite(scores).all(),'invalid scores')
  ranks=sorted(range(len(self.ids)),key=lambda i:(-float(scores[i]),i))
  return [(self.ids[i],min(1.0,max(0.0,float(scores[i])))) for i in ranks[:top_k] if scores[i]>0]

def load_index(directory,expected_version,model_path=None):
 root=Path(directory);require(root.is_dir() and not root.is_symlink(),'invalid index directory')
 require((root/'manifest.json').is_file() and not (root/'manifest.json').is_symlink() and (root/'manifest.json').stat().st_size<=65536,'invalid manifest file')
 manifest=strict_json((root/'manifest.json').read_bytes());version=manifest.pop('indexVersion',None)
 require(re.fullmatch('[0-9a-f]{64}',expected_version or '') and version==expected_version==digest(encoded(manifest)) and manifest['schemaVersion']==1,'index version mismatch')
 actual=set()
 for p in root.rglob('*'):
  require(not p.is_symlink(),'index symlink prohibited')
  if p.is_file() and p.relative_to(root).as_posix() not in ('manifest.json','validation.json'):actual.add(p.relative_to(root).as_posix())
 require(actual==set(manifest['files']),'index file inventory mismatch')
 for name,sha in manifest['files'].items():
  require((root/safe_path(name)).stat().st_size<=32*1024*1024,'oversize index artifact')
  require(digest((root/name).read_bytes())==sha,'index artifact hash drift')
 require(manifest['runtimeVersions']==runtime_versions(manifest['vector']['backend']),'runtime package version drift')
 corpus=FrozenCorpus(root,manifest);snapshot=GraphSnapshot(corpus)
 require(encoded(snapshot.export())==(root/'graph.json').read_bytes(),'graph snapshot mismatch')
 vector=FrozenVector(root,manifest,corpus,model_path)
 identity={k:manifest[k] for k in ('bundleSha256','metadataSha256')};identity.update(indexVersion=version,modelRevision=manifest['vector']['modelRevision'])
 return SimpleNamespace(root=root,version=version,manifest=manifest,corpus=corpus,snapshot=snapshot,vector=vector,identity=identity)
