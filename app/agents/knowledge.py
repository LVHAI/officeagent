from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.rag import HybridRetriever, KnowledgeChunk, build_context


@dataclass(frozen=True)
class KnowledgeResult:
    """Knowledge Agent 对外输出，确保答案上下文和来源一起传递。"""

    query: str
    chunks: list[KnowledgeChunk]
    context: str


class KnowledgePipeline:
    """确定性的 RAG Pipeline；Agent Runtime 只负责理解任务，不负责重写检索逻辑。"""

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
