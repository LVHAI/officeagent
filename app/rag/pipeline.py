from __future__ import annotations

from collections.abc import Sequence

from app.rag.embedding import EmbeddingService
from app.rag.models import DocumentChunk, RetrievalResult, Source
from app.rag.milvus import MilvusRepository
from app.rag.query_rewrite import QueryRewriter
from app.rag.rerank import Reranker
from app.rag.retriever import HybridRetriever


class RetrievalPipeline:
    """RAG 检索编排层：查询改写 + BM25 + Milvus + 重排 + Parent Context + 引用。"""

    def __init__(self, chunks: Sequence[DocumentChunk], *, embeddings: EmbeddingService | None = None, vector_store: MilvusRepository | None = None, reranker: Reranker | None = None, query_rewriter: QueryRewriter | None = None) -> None:
        self.retriever = HybridRetriever(chunks)
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.reranker = reranker or Reranker()
        self.query_rewriter = query_rewriter or QueryRewriter()
        self.chunks = list(chunks)

    @staticmethod
    def expand_parent_context(results: Sequence[RetrievalResult], chunks: Sequence[DocumentChunk]) -> list[RetrievalResult]:
        """Restore parent summaries for child hits without replacing the matched child."""
        by_id = {chunk.id: chunk for chunk in chunks}
        expanded = list(results)
        seen = {result.chunk.id for result in expanded}
        for result in results:
            parent_id = result.chunk.metadata.get("parent_id")
            if not parent_id or parent_id in seen:
                continue
            parent = by_id.get(str(parent_id))
            if parent is None:
                continue
            expanded.append(RetrievalResult(parent, result.score * 0.99, "parent"))
            seen.add(parent.id)
        return expanded

    async def retrieve_async(self, query: str, *, limit: int = 5, metadata_filter: dict[str, str] | None = None) -> list[RetrievalResult]:
        rewritten_query = self.query_rewriter.rewrite(query)
        lexical = self.retriever.bm25(rewritten_query, limit=max(limit * 10, 20), metadata_filter=metadata_filter)
        routes: list[Sequence[RetrievalResult]] = [lexical]
        if self.embeddings is not None and self.vector_store is not None:
            try:
                vector = await self.embeddings.embed_query(rewritten_query)
                routes.append(self.vector_store.search(vector, limit=max(limit * 10, 20), metadata_filter=metadata_filter))
            except Exception:
                pass
        merged = self.retriever.merge_and_rerank(routes, limit=max(limit * 2, 10))
        reranked = self.reranker.rerank(rewritten_query, merged, limit=limit)
        return self.expand_parent_context(reranked, self.chunks)

    def retrieve(self, query: str, *, limit: int = 5, metadata_filter: dict[str, str] | None = None) -> list[RetrievalResult]:
        rewritten_query = self.query_rewriter.rewrite(query)
        lexical = self.retriever.bm25(rewritten_query, limit=max(limit * 10, 20), metadata_filter=metadata_filter)
        merged = self.retriever.merge_and_rerank([lexical], limit=max(limit * 2, 10))
        reranked = self.reranker.rerank(rewritten_query, merged, limit=limit)
        return self.expand_parent_context(reranked, self.chunks)

    @staticmethod
    def build_context(results: Sequence[RetrievalResult]) -> str:
        blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            source = result.chunk.source or Source(chunk_id=result.chunk.id)
            blocks.append(f"[{index}] {RetrievalPipeline._format_source(source)}\n{result.chunk.content}")
        return "\n\n".join(blocks)

    @staticmethod
    def _format_source(source: Source) -> str:
        parts = [source.document, f"page={source.page}" if source.page is not None else None, source.section, source.article, f"chunk={source.chunk_id}" if source.chunk_id else None]
        return " | ".join(part for part in parts if part) or "source=unknown"
