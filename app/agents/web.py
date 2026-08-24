from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class WebSource:
    url: str
    title: str
    source: str
    retrieved_at: str


def normalize_tavily_results(response: Any) -> list[WebSource]:
    """将 Tavily 返回统一为可审计 Source，兼容 SDK dict/list 两种返回形态。"""
    items = response.get("results", []) if isinstance(response, dict) else response or []
    now = datetime.now(timezone.utc).isoformat()
    return [
        WebSource(
            url=str(item.get("url", "")),
            title=str(item.get("title", "")),
            source=str(item.get("source", "tavily")),
            retrieved_at=now,
        )
        for item in items
        if item.get("url")
    ]
