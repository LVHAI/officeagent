from __future__ import annotations

from collections.abc import Sequence

from pymilvus import DataType, MilvusClient

from app.core.config import Settings, settings
from app.rag.models import DocumentChunk, RetrievalResult


class MilvusRepository:
    def __init__(self, current: Settings = settings, collection: str = "officeagent_chunks") -> None:
        self.collection = collection
        self.client = MilvusClient(uri=f"http://{current.milvus_host}:{current.milvus_port}")

    def ensure_collection(self, dimension: int) -> None:
        if self.client.has_collection(self.collection):
            return
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
        self.client.create_collection(self.collection, schema=schema, index_params=index_params)

    def insert(self, chunks: Sequence[DocumentChunk], vectors: Sequence[Sequence[float]]) -> None:
        rows = []
        for chunk, vector in zip(chunks, vectors):
            rows.append({"id": chunk.id, "vector": list(vector), "content": chunk.content, **chunk.metadata})
        if rows:
            self.client.insert(self.collection, rows)

    def search(self, vector: Sequence[float], limit: int = 50) -> list[RetrievalResult]:
        result = self.client.search(
            collection_name=self.collection,
            data=[list(vector)],
            limit=limit,
            output_fields=["content", "id"],
        )
        return [
            RetrievalResult(
                chunk=DocumentChunk(id=str(hit["id"]), content=hit["entity"]["content"]),
                score=float(hit["distance"]),
                route="vector",
            )
            for hit in result[0]
        ]
