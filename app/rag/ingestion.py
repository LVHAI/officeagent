from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.rag.embedding import EmbeddingService
from app.rag.milvus import MilvusRepository
from app.rag.models import DocumentChunk


class RAGIngestionPipeline:
    """Deterministic ingestion boundary: chunks -> embeddings -> Milvus."""

    def __init__(self, *, embedder: EmbeddingService, vector_store: MilvusRepository | None) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    @staticmethod
    def normalize_metadata(
        chunk: DocumentChunk,
        *,
        department: str | None = None,
        chapter: str | None = None,
        page: int | None = None,
    ) -> DocumentChunk:
        metadata = dict(chunk.metadata)
        metadata.setdefault("document", metadata.get("document", "unknown"))
        metadata.setdefault("doc_type", "semantic")
        metadata.setdefault("chunk_type", metadata.get("doc_type", "semantic"))
        if department is not None:
            metadata["department"] = department
        if chapter is not None:
            metadata["chapter"] = chapter
        if page is not None:
            metadata["page"] = page
        return replace(chunk, metadata=metadata)

    def persist(self, chunks: Sequence[DocumentChunk]) -> int:
        values = list(chunks)
        if not values:
            return 0
        vectors = self.embedder.embed_documents_sync([chunk.content for chunk in values])
        if len(vectors) != len(values):
            raise ValueError("embedding count must match chunk count")
        if self.vector_store is None:
            return len(values)
        dimension = len(vectors[0])
        if dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError("all embedding vectors must have the same dimension")
        self.vector_store.reset_collection(dimension)
        self.vector_store.insert(values, vectors)
        return len(values)
