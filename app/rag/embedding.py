from __future__ import annotations

from collections.abc import Sequence

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        kwargs: dict = {}
        if settings.llm_api_key:
            kwargs["api_key"] = settings.llm_api_key
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small", **kwargs)

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._embeddings.aembed_documents(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        return await self._embeddings.aembed_query(text)
