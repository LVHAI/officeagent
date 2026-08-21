from __future__ import annotations

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
