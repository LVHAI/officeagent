from __future__ import annotations

from collections.abc import Mapping, Sequence

from pymilvus import DataType, MilvusClient

from app.core.config import Settings, settings
from app.rag.models import DocumentChunk, RetrievalResult, Source


class MilvusRepository:
    """Milvus 向量仓储：负责集合生命周期、批量写入和带过滤的向量检索。"""

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
        """批量写入文档向量；metadata 使用 Milvus dynamic fields 保存。"""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        rows = [
            {
                "id": chunk.id,
                "vector": list(vector),
                "content": chunk.content,
                **chunk.metadata,
            }
            for chunk, vector in zip(chunks, vectors)
        ]
        if rows:
            self.client.insert(self.collection, rows)

    def search(
        self,
        vector: Sequence[float],
        limit: int = 50,
        metadata_filter: Mapping[str, str] | None = None,
    ) -> list[RetrievalResult]:
        """执行 Milvus 向量搜索，并在数据库侧应用 metadata filter。"""
        kwargs: dict = {
            "collection_name": self.collection,
            "data": [list(vector)],
            "limit": limit,
            "output_fields": ["content", "id"],
        }
        if metadata_filter:
            # Milvus expression 使用字符串字面量；值经过转义后避免破坏表达式。
            expressions = [
                f'{key} == "{str(value).replace(chr(92), chr(92) + chr(92)).replace(chr(34), chr(92) + chr(34))}"'
                for key, value in metadata_filter.items()
            ]
            kwargs["filter"] = " and ".join(expressions)

        result = self.client.search(**kwargs)
        output: list[RetrievalResult] = []
        for hit in result[0]:
            entity = hit["entity"]
            metadata = {
                key: value
                for key, value in entity.items()
                if key not in {"id", "content", "vector"}
            }
            output.append(
                RetrievalResult(
                    chunk=DocumentChunk(
                        id=str(hit["id"]),
                        content=entity["content"],
                        metadata=metadata,
                        source=Source(chunk_id=str(hit["id"])),
                    ),
                    score=float(hit["distance"]),
                    route="vector",
                )
            )
        return output
