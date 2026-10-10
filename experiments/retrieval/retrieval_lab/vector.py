"""Character TF-IDF is lexical sparse-vector retrieval, not semantic embedding."""
from pathlib import Path
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from .corpus import require, digest, safe_path


class LexicalVector:
    name = 'character-tfidf-cosine'
    semantic = False

    def __init__(self, corpus):
        self.ids = corpus.evidence_ids
        self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4), lowercase=True, norm='l2')
        self.matrix = self.vectorizer.fit_transform(
            [p + '\n' + corpus.documents[p].content for p in self.ids])

    def search(self, query, top_k=3):
        require(isinstance(top_k, int) and 1 <= top_k <= 9, 'top_k must be 1..9')
        scores = (self.matrix @ self.vectorizer.transform([query]).T).toarray().ravel()
        ranks = sorted(range(len(self.ids)), key=lambda i: (-float(scores[i]), i))
        return [(self.ids[i], float(scores[i])) for i in ranks[:top_k] if scores[i] > 0]


class LocalSemanticVector:
    """Opt-in local weights only; never downloads/installs a model. Not run in baseline."""
    name = 'local-sentence-transformer'
    semantic = True

    def __init__(self, corpus, model_path, *, enabled=False):
        require(enabled, 'semantic adapter disabled; explicit enable required')
        model_path = Path(model_path).resolve()
        manifest = json.loads((model_path / 'retrieval-model-manifest.json').read_text())
        require(re.fullmatch(r'[0-9a-f]{40}', manifest['revision']), 'pin model revision')
        files = {p.relative_to(model_path).as_posix() for p in model_path.rglob('*')
                 if p.is_file() and p.name != 'retrieval-model-manifest.json'}
        require(files == set(manifest['files']), 'model artifact inventory mismatch')
        for name, expected in manifest['files'].items():
            require(digest((model_path / safe_path(name)).read_bytes()) == expected, 'model artifact hash drift')
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(str(model_path), device='cpu', local_files_only=True)
        self.ids = corpus.evidence_ids
        self.matrix = self.model.encode([corpus.documents[p].content for p in self.ids],
                                        normalize_embeddings=True, convert_to_numpy=True)
        self.provenance = manifest

    def search(self, query, top_k=3):
        require(isinstance(top_k, int) and 1 <= top_k <= 9, 'top_k must be 1..9')
        vector = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        scores = self.matrix @ vector
        ranks = sorted(range(len(self.ids)), key=lambda i: (-float(scores[i]), i))
        return [(self.ids[i], float(scores[i])) for i in ranks[:top_k] if scores[i] > 0]
