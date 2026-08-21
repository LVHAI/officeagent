"""
RAG 检索模块

负责统一封装企业知识库检索接口。
后续可以接入 Milvus、Elasticsearch、BM25 等真实检索服务。
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class RetrievalResult:
    """检索结果，保留来源信息用于后续 Source Trace。"""

    content: str
    score: float
    metadata: Dict[str, Any]


class Retriever:
    """统一检索接口。

    设计目的：
    1. 屏蔽底层向量数据库差异。
    2. 支持多路召回。
    3. 支持异常降级。
    """

    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        try:
            # TODO: 接入 Milvus / BM25 / Metadata Filter
            return []
        except Exception as exc:
            # 检索失败不能直接导致 Agent 崩溃，返回空结果交给上层处理。
            return []
