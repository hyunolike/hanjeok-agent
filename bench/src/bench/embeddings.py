"""Pinned local multilingual embeddings; no model loads during import."""

from collections.abc import Sequence

from langchain_core.embeddings import Embeddings

from bench.graph.store import EMBEDDING_DIM

MODEL = "intfloat/multilingual-e5-large"
REVISION = "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"


class LocalEmbedder(Embeddings):
    def __init__(self, *, encoder=None):
        self._encoder = encoder

    def _encode(self, texts: Sequence[str], prefix: str) -> list[list[float]]:
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(MODEL, revision=REVISION, device="cpu")
        vectors = self._encoder.encode(
            [prefix + text for text in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=16,
            show_progress_bar=False,
        )
        rows = [list(map(float, row)) for row in vectors]
        if any(len(row) != EMBEDDING_DIM for row in rows):
            raise ValueError("local model does not match the graph embedding dimensions")
        return rows

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embed_documents(list(texts))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, "passage: ") if texts else []

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], "query: ")[0]
