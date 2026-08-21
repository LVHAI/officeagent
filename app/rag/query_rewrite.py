from __future__ import annotations

import re


class QueryRewriter:
    """轻量查询改写器：规范化中英文空白并去除明显噪声。"""

    _WHITESPACE = re.compile(r"\s+")

    def rewrite(self, query: str) -> str:
        # 查询改写保持确定性，避免本地测试依赖额外 LLM 调用。
        normalized = self._WHITESPACE.sub(" ", query.strip())
        return normalized
