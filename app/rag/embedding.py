from __future__ import annotations

from collections.abc import Sequence

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


class EmbeddingService:
    """统一封装 Embedding Provider，支持 OpenAI-compatible API。"""

    def __init__(self) -> None:
        kwargs: dict = {}
        if settings.llm_api_key:
            kwargs["api_key"] = settings.llm_api_key
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        # Embedding 模型通过配置注入，避免将模型名称写死在 RAG Pipeline 中。
        self._embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            **kwargs,
        )

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """批量生成文档向量，供索引构建使用。"""
        return await self._embeddings.aembed_documents(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        """生成查询向量，供 Milvus 向量检索使用。"""
        return await self._embeddings.aembed_query(text)
