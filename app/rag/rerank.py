from __future__ import annotations

import re
from collections.abc import Sequence

from app.rag.models import RetrievalResult


class Reranker:
    """轻量确定性重排器；后续可替换为 Cross-Encoder 或 LLM Reranker。"""

    @staticmethod
    def _terms(text: str) -> set[str]:
        # 中文按单字拆分，英文按单词拆分，保证本地开发无需额外模型。
        return set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower()))

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        limit: int = 5,
    ) -> list[RetrievalResult]:
        query_terms = self._terms(query)
        scored: list[tuple[float, RetrievalResult]] = []
        for result in results:
            content_terms = self._terms(result.chunk.content)
            overlap = len(query_terms & content_terms) / max(len(query_terms), 1)
            # 保留原始检索分数，同时引入查询词覆盖率改善排序。
            score = 0.65 * result.score + 0.35 * overlap
            scored.append((score, result))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [result for _, result in scored[:limit]]
