from __future__ import annotations

import re
from collections.abc import Iterable

from app.rag.models import DocumentChunk


def policy_nodes(text: str, document: str) -> list[DocumentChunk]:
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
