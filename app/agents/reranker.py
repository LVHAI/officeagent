from __future__ import annotations

from app.agents.rag import KnowledgeChunk


class KeywordReranker:
    """轻量可替换 Reranker：先保证本地可运行，再可替换为 Cross-Encoder。"""

    def rerank(self, query: str, chunks: list[KnowledgeChunk], top_k: int = 5) -> list[KnowledgeChunk]:
        if not query.strip() or top_k <= 0:
            return []

        terms = set(query.lower().split())

        def score(chunk: KnowledgeChunk) -> float:
            tokens = set(chunk.text.lower().split())
            overlap = len(terms & tokens)
            return overlap + chunk.score

        return sorted(chunks, key=score, reverse=True)[:top_k]
