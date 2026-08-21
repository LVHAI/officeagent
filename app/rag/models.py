from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Source:
    document: str | None = None
    page: int | None = None
    section: str | None = None
    article: str | None = None
    chunk_id: str | None = None


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source: Source | None = None


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float
    route: str
