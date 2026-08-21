from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VectorSearchResult:
    """向量检索结果，统一保存 chunk 与来源信息。"""

    chunk_id: str
    text: str
    document: str
    score: float
    page: int | None = None
    section: str | None = None


class MilvusVectorStore:
    """Milvus 轻量适配层；连接和 collection 由调用方控制，便于本地调试和测试替换。"""

    def __init__(self, collection: Any) -> None:
        self.collection = collection

    def search(self, query_vector: list[float], top_k: int = 5, expr: str | None = None) -> list[VectorSearchResult]:
        if not query_vector or top_k <= 0:
            return []

        results = self.collection.search(
            data=[query_vector],
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "text", "document", "page", "section"],
        )
        hits = results[0] if results else []
        return [
            VectorSearchResult(
                chunk_id=str(hit.entity.get("chunk_id")),
                text=str(hit.entity.get("text", "")),
                document=str(hit.entity.get("document", "")),
                score=float(hit.distance),
                page=hit.entity.get("page"),
                section=hit.entity.get("section"),
            )
            for hit in hits
        ]


def create_milvus_collection_schema() -> list[dict[str, Any]]:
    """返回统一字段定义，实际 Collection 创建由基础设施初始化层完成。"""
    return [
        {"name": "chunk_id", "dtype": "VARCHAR", "max_length": 128, "primary_key": True},
        {"name": "document", "dtype": "VARCHAR", "max_length": 512},
        {"name": "text", "dtype": "VARCHAR", "max_length": 8192},
        {"name": "page", "dtype": "INT64"},
        {"name": "section", "dtype": "VARCHAR", "max_length": 512},
        {"name": "embedding", "dtype": "FLOAT_VECTOR"},
    ]
