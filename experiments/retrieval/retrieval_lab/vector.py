"""Lexical TF-IDF and opt-in, pinned local multilingual semantic retrieval."""
from pathlib import Path
import json
import re
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from .corpus import require, digest, safe_path


class LexicalVector:
    name = 'character-tfidf-cosine'
    semantic = False

    def __init__(self, corpus):
        self.ids = corpus.evidence_ids
        self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), lowercase=True, norm='l2')
        self.matrix = self.vectorizer.fit_transform([p+'\n'+corpus.documents[p].content for p in self.ids])

    def search(self, query, top_k=3):
        require(isinstance(top_k, int) and 1 <= top_k <= 9, 'top_k must be 1..9')
        scores = (self.matrix @ self.vectorizer.transform([query]).T).toarray().ravel()
        ranks = sorted(range(len(self.ids)), key=lambda i: (-float(scores[i]), i))
        return [(self.ids[i], float(scores[i])) for i in ranks[:top_k] if scores[i] > 0]


class LocalSemanticVector:
    """CPU safetensors, built-in modules only; no download or remote model code."""
    name = 'local-sentence-transformer'
    semantic = True

    def __init__(self, corpus, model_path, *, enabled=False):
        require(enabled, 'semantic adapter disabled; explicit enable required')
        model_path = Path(model_path).resolve()
        manifest = json.loads((model_path/'retrieval-model-manifest.json').read_text())
        require(re.fullmatch(r'[0-9a-f]{40}', manifest['revision']), 'pin model revision')
        files = {p.relative_to(model_path).as_posix() for p in model_path.rglob('*')
                 if p.is_file() and p.name != 'retrieval-model-manifest.json'}
        require(files == set(manifest['files']), 'model artifact inventory mismatch')
        for name, expected in manifest['files'].items():
            require(Path(name).suffix in ('.json','.txt','.md','.safetensors'), 'unsafe model artifact type')
            require(digest((model_path/safe_path(name)).read_bytes()) == expected, 'model artifact hash drift')
        modules=json.loads((model_path/'modules.json').read_text())
        require([m['type'] for m in modules] == ['sentence_transformers.models.Transformer',
                'sentence_transformers.models.Pooling','sentence_transformers.models.Dense'], 'unsupported model modules')
        require('auto_map' not in json.loads((model_path/'config.json').read_text()), 'remote model code prohibited')
        import os
        os.environ["HF_HUB_OFFLINE"]="1"
        os.environ["TRANSFORMERS_OFFLINE"]="1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"]="1"
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(1)
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        self.model=SentenceTransformer(str(model_path),device='cpu',local_files_only=True,trust_remote_code=False)
        self.ids=corpus.evidence_ids
        tokenizer=self.model.tokenizer
        payload=self.model.max_seq_length-tokenizer.num_special_tokens_to_add(pair=False)
        require(payload >= 16, 'unexpected token window')
        stride=payload-14
        chunks,owners,counts=[],[],[]
        for i,path in enumerate(self.ids):
            tokens=tokenizer.encode(path+'\n'+corpus.documents[path].content,add_special_tokens=False,verbose=False)
            count,start=0,0
            while start < len(tokens):
                end=min(start+payload,len(tokens))
                while end > start:
                    text=tokenizer.decode(tokens[start:end],clean_up_tokenization_spaces=False)
                    length=len(tokenizer.encode(text,verbose=False))
                    if length <= self.model.max_seq_length: break
                    end -= max(1,length-self.model.max_seq_length)
                require(end > start, 'cannot produce an untruncated chunk')
                chunks.append(text);owners.append(i);count+=1
                if end==len(tokens): break
                start=end-min(14,end-start-1)
            counts.append(count)
        encoded=self.model.encode(chunks,batch_size=16,normalize_embeddings=True,convert_to_numpy=True,
                                  show_progress_bar=False)
        matrix=np.stack([encoded[np.array(owners)==i].mean(axis=0) for i in range(len(self.ids))]).astype('float32')
        matrix /= np.linalg.norm(matrix,axis=1,keepdims=True)
        self.matrix=matrix
        self.provenance=dict(**manifest,device='cpu',dimension=int(matrix.shape[1]),
                             maxSequenceTokens=self.model.max_seq_length,payloadTokens=payload,nominalStrideTokens=stride,overlapTokens=14,boundaryAdjustment="shrink until retokenized length fits",
                             documentChunkCounts=dict(zip(self.ids,counts)),totalChunks=len(chunks),
                             pooling='mean of normalized chunk embeddings, then L2 normalize',
                             documentMatrixSha256=digest(matrix.tobytes()),trustRemoteCode=False,
                             localFilesOnly=True,weightsFormat='safetensors',torchThreads=1)

    @lru_cache(maxsize=256)
    def query_vector(self, query):
        require(len(self.model.tokenizer.encode(query)) <= self.model.max_seq_length, 'query would be truncated')
        return self.model.encode([query],normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)[0]

    def search(self, query, top_k=3):
        require(isinstance(top_k, int) and 1 <= top_k <= 9, 'top_k must be 1..9')
        scores=self.matrix @ self.query_vector(query)
        ranks=sorted(range(len(self.ids)),key=lambda i:(-float(scores[i]),i))
        return [(self.ids[i],float(scores[i])) for i in ranks[:top_k] if scores[i]>0]
