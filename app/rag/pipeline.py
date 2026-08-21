from __future__ import annotations

from collections.abc import Sequence

from app.rag.embedding import EmbeddingService
from app.rag.models import DocumentChunk, RetrievalResult, Source
from app.rag.milvus import MilvusRepository
from app.rag.retriever import HybridRetriever


class RetrievalPipeline:
    """RAG 检索编排层：BM25 + Milvus 向量检索后统一合并。"""

    def __init__(
        self,
        chunks: Sequence[DocumentChunk],
        *,
        embeddings: EmbeddingService | None = None,
        vector_store: MilvusRepository | None = None,
    ) -> None:
        self.retriever = HybridRetriever(chunks)
        self.embeddings = embeddings
        self.vector_store = vector_store

    async def retrieve_async(
        self,
        query: str,
        *,
        limit: int = 5,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        """执行混合检索；向量检索失败时保留关键词结果，避免单路故障导致整个 RAG 失败。"""
        lexical = self.retriever.bm25(
            query,
            limit=max(limit * 10, 20),
            metadata_filter=metadata_filter,
        )
        routes: list[Sequence[RetrievalResult]] = [lexical]

        if self.embeddings is not None and self.vector_store is not None:
            try:
                vector = await self.embeddings.embed_query(query)
                routes.append(
                    self.vector_store.search(
                        vector,
                        limit=max(limit * 10, 20),
                        metadata_filter=metadata_filter,
                    )
                )
            except Exception:
                # 向量服务短暂不可用时降级到 BM25，保证基础检索能力仍可用。
                pass

        return self.retriever.merge_and_rerank(routes, limit=limit)

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        # 保留同步 BM25 接口，方便单元测试和纯本地开发场景使用。
        lexical = self.retriever.bm25(
            query,
            limit=max(limit * 10, 20),
            metadata_filter=metadata_filter,
        )
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
        parts = [
            source.document,
            f"page={source.page}" if source.page is not None else None,
            source.section,
            source.article,
            f"chunk={source.chunk_id}" if source.chunk_id else None,
        ]
        return " | ".join(part for part in parts if part) or "source=unknown"
