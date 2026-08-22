from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Sequence

from app.rag.models import DocumentChunk


_POLICY_KEY_PATTERN = re.compile(r"^(?P<document>.+?)\s+(?P<article>第[一二三四五六七八九十百千万0-9]+条)$")
_SENTENCE_PATTERN = re.compile(r"(?<=[。！？!?；;])\s*|\n{2,}")


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


def split_sentences(text: str) -> list[str]:
    """将 Markdown/纯文本拆成适合语义比较的最小语义单元。"""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    units = [part.strip() for part in _SENTENCE_PATTERN.split(text) if part.strip()]
    return units


def semantic_chunks(
    sentences: Iterable[str],
    threshold: float = 0.75,
    embedder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
    max_chars: int = 1200,
) -> list[str]:
    """按相邻文本 embedding 相似度切分语义块。

    threshold 越高，越容易在语义变化处断开。传入 embedder 时执行真正的
    embedding 相似度边界判断；未提供 embedder 时保留确定性的长度 fallback，
    避免测试和离线环境依赖外部 embedding 服务。
    """
    if not 0 < threshold <= 1:
        raise ValueError("threshold 必须在 (0, 1] 范围内")
    units = [s.strip() for s in sentences if s and s.strip()]
    if not units:
        return []

    if embedder is None:
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for unit in units:
            if current and current_len + len(unit) + 1 > max_chars:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            current.append(unit)
            current_len += len(unit) + (1 if current_len else 0)
        if current:
            chunks.append(" ".join(current))
        return chunks

    vectors = [list(vector) for vector in embedder(units)]
    if len(vectors) != len(units):
        raise ValueError("embedder 返回的向量数量必须与输入语义单元数量一致")
    if any(not vector for vector in vectors):
        raise ValueError("embedder 返回的向量不能为空")

    def cosine(a: Sequence[float], b: Sequence[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    chunks: list[str] = []
    current = [units[0]]
    for index in range(1, len(units)):
        similarity = cosine(vectors[index - 1], vectors[index])
        candidate = " ".join(current + [units[index]])
        if similarity < threshold or len(candidate) > max_chars:
            chunks.append(" ".join(current))
            current = [units[index]]
        else:
            current.append(units[index])
    chunks.append(" ".join(current))
    return chunks


def semantic_nodes(
    text: str,
    document: str,
    threshold: float = 0.75,
    embedder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
    max_chars: int = 1200,
) -> list[DocumentChunk]:
    """解析 semantic/*.md 等文档并生成带 metadata 的语义 Chunk。"""
    units = split_sentences(text)
    chunks = semantic_chunks(units, threshold=threshold, embedder=embedder, max_chars=max_chars)
    return [
        DocumentChunk(
            id=f"semantic_{index:05d}",
            content=content,
            metadata={"document": document, "doc_type": "semantic", "chunk_index": index},
        )
        for index, content in enumerate(chunks, start=1)
    ]
