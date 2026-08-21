"""
混合检索模块

组合：
- 向量检索
- BM25关键词检索
- Metadata过滤

用于提高企业知识问答召回率。
"""

from typing import List

from .retriever import RetrievalResult


class HybridSearcher:
    """多路召回融合器。"""

    async def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        # 后续接入 Vector DB + BM25
        # 当前保留统一接口，方便 LangGraph Agent 调用。
        return []

    def merge(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """合并不同检索源结果。

        实际实现中这里会进行去重和排序。
        """
        return results
