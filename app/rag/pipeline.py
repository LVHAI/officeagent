from __future__ import annotations

from collections.abc import Sequence

from app.rag.models import DocumentChunk, RetrievalResult, Source
from app.rag.retriever import HybridRetriever


class RetrievalPipeline:
    """RAG 检索编排层，统一执行 BM25、多路结果合并和来源构建。"""

    def __init__(self, chunks: Sequence[DocumentChunk]) -> None:
        self.retriever = HybridRetriever(chunks)

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        # 当前基础实现使用 BM25；向量检索结果可通过 routes 直接接入同一个合并入口。
        lexical = self.retriever.bm25(query, limit=max(limit * 10, 20), metadata_filter=metadata_filter)
        return self.retriever.merge_and_rerank([lexical], limit=limit)

    @staticmethod
    def build_context(results: Sequence[RetrievalResult]) -> str:
        """构造带引用标记的上下文，避免生成答案时丢失文档来源。"""
        blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            source = result.chunk.source or Source(chunk_id=result.chunk.id)
            citation = RetrievalPipeline._format_source(source)
            blocks.append(f"[{index}] {citation}\n{result.chunk.content}")
        return "\n\n".join(blocks)

    @staticmethod
    def _format_source(source: Source) -> str:
        parts = [source.document, f"page={source.page}" if source.page is not None else None,
                 source.section, source.article, f"chunk={source.chunk_id}" if source.chunk_id else None]
        return " | ".join(part for part in parts if part) or "source=unknown"
