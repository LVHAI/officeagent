from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from app.core.config import settings


class EmbeddingService:
    """DashScope Embedding HTTP client.

    DashScope's OpenAI-compatible embedding endpoint accepts raw text. We do
    not use LangChain's OpenAIEmbeddings here because its tokenizer path can
    interpret the DashScope model name as a Hugging Face tokenizer identifier.
    """

    def __init__(self, transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for DashScope embeddings")
        self._url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
        self._headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = settings.llm_timeout_seconds
        self._batch_size = 10
        self._transport = transport

    @staticmethod
    def _vectors(payload: dict[str, Any], expected: int) -> list[list[float]]:
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected:
            raise RuntimeError("DashScope embedding response has invalid data length")

        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors: list[list[float]] = []
        for item in ordered:
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise RuntimeError("DashScope embedding response contains an empty vector")
            vectors.append([float(value) for value in embedding])
        return vectors

    def _request_sync(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": settings.embedding_model,
            "input": list(texts),
            "encoding_format": "float",
        }
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            response = client.post(self._url, headers=self._headers, json=payload)
        if response.is_error:
            detail = response.text
            try:
                error = response.json().get("error", {})
                detail = f"{error.get('code', '')}: {error.get('message', detail)}"
            except ValueError:
                pass
            raise RuntimeError(f"DashScope embedding request failed ({response.status_code}): {detail}")
        return self._vectors(response.json(), len(texts))

    async def _request_async(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": settings.embedding_model,
            "input": list(texts),
            "encoding_format": "float",
        }
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self._url, headers=self._headers, json=payload)
        if response.is_error:
            detail = response.text
            try:
                error = response.json().get("error", {})
                detail = f"{error.get('code', '')}: {error.get('message', detail)}"
            except ValueError:
                pass
            raise RuntimeError(f"DashScope embedding request failed ({response.status_code}): {detail}")
        return self._vectors(response.json(), len(texts))

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Batch document embeddings, respecting DashScope's 10-item limit."""
        values = list(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(values), self._batch_size):
            vectors.extend(await self._request_async(values[start : start + self._batch_size]))
        return vectors

    def embed_documents_sync(self, texts: Sequence[str]) -> list[list[float]]:
        """Synchronous document embeddings for semantic chunk boundary detection."""
        values = list(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(values), self._batch_size):
            vectors.extend(self._request_sync(values[start : start + self._batch_size]))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        """Generate a query vector with the same model used for ingestion."""
        return (await self._request_async([text]))[0]

    def embed_query_sync(self, text: str) -> list[float]:
        """Synchronous query embedding helper."""
        return self._request_sync([text])[0]
