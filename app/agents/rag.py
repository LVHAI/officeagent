from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from rank_bm25 import BM25Okapi

from app.agents.reranker import KeywordReranker


@dataclass(frozen=True)
class KnowledgeChunk:
    """RAG 检索结果的统一结构，保留可审计的来源元数据。"""

    chunk_id: str
    text: str
    document: str
    score: float = 0.0
    page: int | None = None
    section: str | None = None


class HybridRetriever:
    """Hybrid RAG：BM25 + 可注入向量检索，并统一进行 Rerank。"""

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        vector_search: Callable[[str, int], list[KnowledgeChunk]] | None = None,
        reranker: Any | None = None,
    ) -> None:
        self._chunks = chunks
        self._vector_search = vector_search
        self._reranker = reranker or KeywordReranker()
        self._bm25 = BM25Okapi([chunk.text.lower().split() for chunk in chunks]) if chunks else None

    def retrieve(self, query: str, top_k: int = 5) -> list[KnowledgeChunk]:
        if not query.strip() or top_k <= 0:
            return []

        candidates: dict[str, KnowledgeChunk] = {}
        if self._bm25 is not None:
            scores = self._bm25.get_scores(query.lower().split())
            for index in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]:
                chunk = self._chunks[index]
                candidates[chunk.chunk_id] = KnowledgeChunk(
                    **{**chunk.__dict__, "score": float(scores[index])}
                )

        if self._vector_search is not None:
            for chunk in self._vector_search(query, top_k):
                existing = candidates.get(chunk.chunk_id)
                # 混合检索不直接覆盖 BM25 分数，避免一个来源完全吞掉另一个来源。
                if existing is None or chunk.score > existing.score:
                    candidates[chunk.chunk_id] = chunk

        return self._reranker.rerank(query, list(candidates.values()), top_k=top_k)


def build_context(chunks: list[KnowledgeChunk]) -> str:
    """生成带来源标记的上下文，避免回答阶段丢失 Citation。"""
    return "\n\n".join(
        f"[{chunk.chunk_id}] {chunk.document}"
        f"{f' p.{chunk.page}' if chunk.page is not None else ''}"
        f"{f' / {chunk.section}' if chunk.section else ''}\n{chunk.text}"
        for chunk in chunks
    )
