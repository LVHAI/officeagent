"""
Reranker 模块

用于对初步召回结果进行二次排序，提高最终上下文质量。
"""

from typing import List

from .retriever import RetrievalResult


class Reranker:
    """重排序接口。"""

    async def rerank(
        self,
        query: str,
        documents: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        # 未来接入 Cross Encoder / LLM Reranker。
        return sorted(
            documents,
            key=lambda item: item.score,
            reverse=True,
        )
