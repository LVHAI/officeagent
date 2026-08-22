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
    """Build parent/child chunks from a Markdown knowledge document.

    The first H1 title is used as the parent when there is no introduction
    before the first H2. Otherwise, the introduction before the first H2 is
    the parent. Every H2 section becomes one child and retains its heading.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("parent-child markdown document cannot be empty")

    sections = list(re.finditer(r"(?m)^##(?!#)\\s+.+?\\s*$", normalized))
    if not sections:
        title_match = re.search(r"(?m)^#(?!#)\\s+(.+?)\\s*$", normalized)
        parent_text = title_match.group(1).strip() if title_match else normalized
        return build_parent_child(document, parent_text, [])

    first_h2 = sections[0]
    introduction = normalized[: first_h2.start()].strip()
    title_match = re.search(r"(?m)^#(?!#)\\s+(.+?)\\s*$", introduction)

    if title_match:
        introduction_without_title = (introduction[: title_match.start()] + introduction[title_match.end() :]).strip()
    else:
        introduction_without_title = introduction

    parent_text = introduction_without_title or (title_match.group(1).strip() if title_match else "")
    if not parent_text:
        raise ValueError("parent-child markdown document must contain a title or introduction")

    children: list[str] = []
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(normalized)
        content = normalized[section.start() : end].strip()
        if content:
            children.append(content)

    if not children:
        raise ValueError("parent-child markdown document must contain at least one H2 section")

    return build_parent_child(document, parent_text, children)
