"""Strategies choose supplied passages; they do not choose prompts or models."""

from neo4j import Driver

from bench.graph.build import Embedder
from bench.graph.query import Passage, expand, vector_search


class GraphStrategy:
    def __init__(
        self,
        driver: Driver,
        embedder: Embedder,
        *,
        k: int = 5,
        min_score: float = 0.75,
        expansion_limit: int = 8,
    ) -> None:
        self.driver, self.embedder = driver, embedder
        self.k, self.min_score, self.expansion_limit = k, min_score, expansion_limit

    def __call__(self, corpus: str, question: str) -> list[Passage]:
        vector = self.embedder.embed_query(question)
        seeds = vector_search(self.driver, corpus, vector, k=self.k, min_score=self.min_score)
        return seeds + expand(self.driver, corpus, seeds, limit=self.expansion_limit)
