from __future__ import annotations

import json
import re
from collections.abc import Iterable

from app.rag.models import DocumentChunk


_POLICY_KEY_PATTERN = re.compile(r"^(?P<document>.+?)\s+(?P<article>第[一二三四五六七八九十百千万0-9]+条)$")


def _policy_json_nodes(text: str) -> list[DocumentChunk] | None:
    """解析标准政策 JSON 数组：[{"法律名称 第X条": "条款正文"}]。"""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        raise ValueError("policy JSON 必须是数组")

    chunks: list[DocumentChunk] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"policy JSON 第 {index} 项必须是对象")
        for key, value in item.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("policy JSON 的 key 和 value 必须都是字符串")
            match = _POLICY_KEY_PATTERN.match(key.strip())
            if not match:
                raise ValueError(f"无效的政策条款 key: {key!r}，格式应为“法律名称 第X条”")
            chunks.append(
                DocumentChunk(
                    id=f"policy_{len(chunks) + 1:05d}",
                    content=f"{key.strip()}：{value.strip()}",
                    metadata={
                        "document": match.group("document").strip(),
                        "doc_type": "policy",
                        "article": match.group("article"),
                    },
                )
            )
    return chunks


def policy_nodes(text: str, document: str) -> list[DocumentChunk]:
    json_nodes = _policy_json_nodes(text)
    if json_nodes is not None:
        return json_nodes

    pattern = re.compile(r"(第[一二三四五六七八九十百0-9]+条[：:]?.*?)(?=第[一二三四五六七八九十百0-9]+条|$)", re.S)
    chunks: list[DocumentChunk] = []
    for index, match in enumerate(pattern.finditer(text), start=1):
        article = re.match(r"(第[一二三四五六七八九十百0-9]+条)", match.group(1))
        article_name = article.group(1) if article else None
        chunks.append(
            DocumentChunk(
                id=f"policy_{index:05d}",
                content=match.group(1).strip(),
                metadata={"document": document, "doc_type": "policy", "article": article_name},
            )
        )
    return chunks


def semantic_chunks(sentences: Iterable[str], threshold: float = 0.75) -> list[str]:
    """Baseline semantic splitter; embedding similarity can replace this boundary heuristic."""
    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(" ".join(current)) > 900:
            chunks.append(" ".join(current))
            current = []
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks
