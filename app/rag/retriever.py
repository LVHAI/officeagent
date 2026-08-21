from __future__ import annotations

import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from app.rag.models import DocumentChunk, RetrievalResult


class HybridRetriever:
    def __init__(self, chunks: Sequence[DocumentChunk]) -> None:
        self.chunks = list(chunks)
        self._bm25 = BM25Okapi([self._tokens(chunk.content) for chunk in self.chunks]) if self.chunks else None

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())

    def bm25(self, query: str, limit: int = 50) -> list[RetrievalResult]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(self._tokens(query))
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:limit]
        return [RetrievalResult(self.chunks[i], float(score), "bm25") for i, score in ranked]

    @staticmethod
    def merge_and_rerank(routes: Sequence[Sequence[RetrievalResult]], limit: int = 5) -> list[RetrievalResult]:
        merged: dict[str, RetrievalResult] = {}
        for route in routes:
            for result in route:
                current = merged.get(result.chunk.id)
                if current is None or result.score > current.score:
                    merged[result.chunk.id] = result
        return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]
