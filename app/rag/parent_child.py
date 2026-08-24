from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from app.rag.models import DocumentChunk


@dataclass(frozen=True)
class ParentChildDocument:
    parent: DocumentChunk
    children: tuple[DocumentChunk, ...]


def build_parent_child(document: str, summary: str, details: list[str]) -> ParentChildDocument:
    parent_id = f"parent_{uuid4()}"
    parent = DocumentChunk(
        id=parent_id,
        content=summary,
        metadata={"document": document, "chunk_type": "parent"},
    )
    children = tuple(
        DocumentChunk(
            id=f"child_{uuid4()}",
            content=detail,
            metadata={"document": document, "chunk_type": "child", "parent_id": parent_id},
        )
        for detail in details
    )
    return ParentChildDocument(parent=parent, children=children)


def build_parent_child_from_markdown(document: str, text: str) -> ParentChildDocument:
    """将单个 Markdown 文档解析为一个 Parent 和多个 Child。

    约定：
    - 第一个 H1（#）是文档标题。
    - 第一个 H2（##）之前的正文是 Parent 内容。
    - 如果 H1 后没有介绍正文，则使用 H1 标题作为 Parent 内容。
    - 每个 H2 区块生成一个 Child，并保留 H2 标题。
    - H3 及更深层级标题属于当前 Child，不单独拆分。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("parent-child markdown document cannot be empty")

    h1_match = re.search(r"(?m)^#(?!#)\s+(.+?)\s*$", normalized)
    h2_matches = list(re.finditer(r"(?m)^##(?!#)\s+.+?\s*$", normalized))

    if not h2_matches:
        parent_text = h1_match.group(1).strip() if h1_match else normalized
        return build_parent_child(document, parent_text, [])

    first_h2 = h2_matches[0]
    introduction = normalized[: first_h2.start()].strip()

    if h1_match and h1_match.start() < first_h2.start():
        introduction_without_title = (
            introduction[: h1_match.start()]
            + introduction[h1_match.end() :]
        ).strip()
    else:
        introduction_without_title = introduction

    parent_text = introduction_without_title or (h1_match.group(1).strip() if h1_match else "")
    if not parent_text:
        raise ValueError("parent-child markdown document must contain a title or introduction")

    children: list[str] = []
    for index, section in enumerate(h2_matches):
        end = h2_matches[index + 1].start() if index + 1 < len(h2_matches) else len(normalized)
        content = normalized[section.start() : end].strip()
        if content:
            children.append(content)

    if not children:
        raise ValueError("parent-child markdown document must contain at least one H2 section")

    return build_parent_child(document, parent_text, children)
