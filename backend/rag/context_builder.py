"""
RAG 上下文构建模块

负责将检索结果转换为大模型可使用的上下文。
包含 Token 控制、结果排序和空结果处理逻辑。
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ContextDocument:
    """上下文文档结构，保留来源信息方便审计。"""

    content: str
    source: dict
    score: float = 0.0


class ContextBuilder:
    """构建 Agent Prompt 所需上下文。"""

    def __init__(self, max_chars: int = 12000):
        self.max_chars = max_chars

    def build(self, documents: List[ContextDocument]) -> str:
        """
        根据评分排序并限制上下文长度。

        防止检索结果过多导致模型上下文溢出。
        """
        if not documents:
            return ""

        documents = sorted(
            documents,
            key=lambda item: item.score,
            reverse=True,
        )

        result = []
        total = 0

        for doc in documents:
            if total + len(doc.content) > self.max_chars:
                break
            result.append(doc.content)
            total += len(doc.content)

        return "\n\n".join(result)
