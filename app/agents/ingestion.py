from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    parent_id: str
    document: str
    text: str
    section: str | None = None
    page: int | None = None


class DocumentParser:
    """支持 TXT/Markdown/PDF/DOCX 的最小统一解析入口。"""

    def parse(self, path: str | Path) -> list[tuple[str, int | None, str]]:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix in {".txt", ".md", ".markdown"}:
            return [(file_path.read_text(encoding="utf-8"), None, file_path.name)]
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            return [(page.extract_text() or "", index + 1, file_path.name) for index, page in enumerate(reader.pages)]
        if suffix == ".docx":
            from docx import Document

            document = Document(str(file_path))
            return [("\n".join(p.text for p in document.paragraphs), None, file_path.name)]
        raise ValueError(f"unsupported document type: {suffix}")


class SemanticChunker:
    """保留 Markdown 标题层级，并生成 parent/child Chunk，避免只做固定字符切分。"""

    def __init__(self, max_chars: int = 1200) -> None:
        self.max_chars = max_chars

    def chunk(self, parsed: list[tuple[str, int | None, str]]) -> list[DocumentChunk]:
        output: list[DocumentChunk] = []
        sequence = 0
        for text, page, document in parsed:
            section = None
            parent_id = f"parent-{sequence}"
            buffer: list[str] = []
            for line in text.splitlines():
                heading = re.match(r"^#{1,6}\s+(.+)$", line.strip())
                if heading:
                    section = heading.group(1).strip()
                if line.strip():
                    buffer.append(line.strip())
                if sum(len(item) + 1 for item in buffer) >= self.max_chars:
                    child = "\n".join(buffer)
                    output.append(DocumentChunk(f"chunk-{sequence}", parent_id, document, child, section, page))
                    sequence += 1
                    buffer = []
            if buffer:
                output.append(DocumentChunk(f"chunk-{sequence}", parent_id, document, "\n".join(buffer), section, page))
                sequence += 1
        return output
