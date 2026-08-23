from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.agents.rag import HybridRetriever, KnowledgeChunk, build_context
from app.core.config import settings
from app.rag.embedding import EmbeddingService
from app.rag.loader import DocumentLoader
from app.rag.models import DocumentChunk
from app.rag.milvus import MilvusRepository
from app.rag.parent_child import build_parent_child_from_markdown
from app.rag.pipeline import RetrievalPipeline
from app.rag.splitter import policy_nodes, semantic_nodes

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAG_ROOT = PROJECT_ROOT / "data"
DEFAULT_COLLECTION = "officeagent_chunks"


@dataclass(frozen=True)
class KnowledgeResult:
    """Knowledge Agent 对外输出，确保答案上下文和来源一起传递。"""

    query: str
    chunks: list[KnowledgeChunk]
    context: str


class KnowledgePipeline:
    """Legacy deterministic RAG facade used by focused unit tests."""

    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    def search(self, query: str, top_k: int = 5) -> KnowledgeResult:
        chunks = self.retriever.retrieve(query, top_k=top_k)
        return KnowledgeResult(query=query, chunks=chunks, context=build_context(chunks))


def create_knowledge_pipeline(
    chunks: list[KnowledgeChunk],
    vector_search: Any | None = None,
    reranker: Any | None = None,
) -> KnowledgePipeline:
    return KnowledgePipeline(HybridRetriever(chunks, vector_search=vector_search, reranker=reranker))


def _document_chunks(corpus_root: Path) -> list[DocumentChunk]:
    """Build the same logical RAG chunks used by ingestion without calling MCP."""
    loader = DocumentLoader()
    documents = loader.load_corpus(corpus_root)
    chunks: list[DocumentChunk] = []
    for document in documents:
        name = document.path.name
        if document.doc_type == "policy":
            chunks.extend(policy_nodes(document.content, name))
        elif document.doc_type == "parent_child":
            parsed = build_parent_child_from_markdown(name, document.content)
            chunks.extend([parsed.parent, *parsed.children])
        elif document.doc_type in {"semantic", "faq"}:
            # Runtime retrieval must not re-run ingestion-time embedding calls.
            # The persisted Milvus vectors remain the semantic route; BM25 gets a
            # deterministic sentence/length fallback for the same source corpus.
            chunks.extend(semantic_nodes(document.content, name, embedder=None))
        else:
            raise ValueError(f"unsupported RAG chunking strategy: {document.doc_type}")
    return chunks


@lru_cache(maxsize=1)
def _runtime_retrieval_pipeline() -> RetrievalPipeline:
    """Create one process-local RAG pipeline; never expose it as an MCP tool."""
    corpus_root = Path(getattr(settings, "rag_corpus_root", str(DEFAULT_RAG_ROOT))).resolve()
    collection = getattr(settings, "rag_collection", DEFAULT_COLLECTION)
    chunks = _document_chunks(corpus_root) if corpus_root.is_dir() else []

    embeddings = EmbeddingService() if settings.llm_api_key else None
    vector_store = MilvusRepository(collection=collection) if embeddings is not None else None
    logger.info(
        "knowledge.rag.pipeline.ready corpus=%s chunks=%d collection=%s vector=%s",
        corpus_root,
        len(chunks),
        collection,
        vector_store is not None,
    )
    return RetrievalPipeline(chunks, embeddings=embeddings, vector_store=vector_store)


@tool
async def knowledge_search(query: str, limit: int = 5) -> str:
    """Search the enterprise Knowledge Base using the deterministic RAG pipeline.

    This tool is owned by Knowledge Agent and is deliberately not an MCP tool.
    It performs query rewrite, BM25, optional Milvus vector retrieval, reranking,
    and returns source-aware context for the answer generator.
    """
    if not query.strip():
        return json.dumps({"query": query, "results": [], "context": "", "sources": []}, ensure_ascii=False)
    if limit <= 0:
        raise ValueError("limit must be positive")

    pipeline = _runtime_retrieval_pipeline()
    results = await pipeline.retrieve_async(query, limit=min(limit, 10))
    context = pipeline.build_context(results)
    sources = []
    for result in results:
        source = result.chunk.source
        sources.append(
            {
                "chunk_id": result.chunk.id,
                "document": source.document if source else result.chunk.metadata.get("document"),
                "page": source.page if source else None,
                "section": source.section if source else None,
                "article": source.article if source else None,
                "score": result.score,
                "route": result.route,
            }
        )
    logger.info(
        "knowledge.rag.search.completed query_length=%d results=%d routes=%s",
        len(query),
        len(results),
        sorted({result.route for result in results}),
    )
    return json.dumps(
        {"query": query, "results": len(results), "context": context, "sources": sources},
        ensure_ascii=False,
    )
