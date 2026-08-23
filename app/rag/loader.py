from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


SUPPORTED_CHUNKING_STRATEGIES = frozenset({"policy", "faq", "parent_child", "semantic"})
SUPPORTED_SOURCE_SUFFIXES = frozenset({".txt", ".md", ".pdf", ".docx", ".json"})


@dataclass(frozen=True)
class LoadedDocument:
    path: Path
    content: str
    doc_type: str


class DocumentLoader:
    """Load supported office documents while preserving PDF page boundaries."""

    def load(self, path: str | Path) -> str:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_SOURCE_SUFFIXES:
            raise ValueError(f"unsupported document type: {suffix}")
        if suffix in {".txt", ".md", ".json"}:
            return file_path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            return "\n\n".join(text for _, text in self.load_pages(file_path) if text)
        if suffix == ".docx":
            return self._load_docx(file_path)
        raise ValueError(f"unsupported document type: {suffix}")

    @staticmethod
    def load_pages(path: str | Path) -> list[tuple[int, str]]:
        """Return one normalized text value per PDF page without losing page numbers."""
        reader = PdfReader(str(path))
        return [
            (index, text)
            for index, page in enumerate(reader.pages, start=1)
            if (text := (page.extract_text() or "").strip())
        ]

    @staticmethod
    def _load_docx(path: Path) -> str:
        document = DocxDocument(str(path))
        blocks: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if text:
                blocks.append(text)
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    blocks.append(" | ".join(cells))
        return "\n".join(blocks)

    def resolve_type(self, path: str | Path, corpus_root: str | Path | None = None) -> str:
        file_path = Path(path)
        if corpus_root is not None:
            root = Path(corpus_root).resolve()
            resolved_path = file_path.resolve()
            try:
                relative = resolved_path.relative_to(root)
            except ValueError:
                return DocumentTypeClassifier().classify(file_path.name, self.load(file_path))
            parts = relative.parts[:-1]
            for part in parts:
                strategy = part.lower()
                if strategy in SUPPORTED_CHUNKING_STRATEGIES:
                    return strategy
            if parts:
                immediate = parts[0].lower()
                if immediate not in {"rag", "data", "documents", "knowledge"}:
                    raise ValueError(
                        f"unsupported RAG chunking strategy folder: {immediate!r}; "
                        f"expected one of {sorted(SUPPORTED_CHUNKING_STRATEGIES)}"
                    )
        return DocumentTypeClassifier().classify(file_path.name, self.load(file_path))

    def load_corpus(self, corpus_root: str | Path) -> list[LoadedDocument]:
        root = Path(corpus_root).resolve()
        if not root.is_dir():
            raise ValueError(f"RAG corpus directory does not exist: {root}")
        documents: list[LoadedDocument] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
                continue
            documents.append(
                LoadedDocument(
                    path=path,
                    content=self.load(path),
                    doc_type=self.resolve_type(path, root),
                )
            )
        return documents


class DocumentTypeClassifier:
    def classify(self, name: str, text: str) -> str:
        normalized = text.lower()
        if "第" in text and "条" in text:
            return "policy"
        if name.lower().endswith((".faq", ".faq.md")) or "faq" in normalized[:200]:
            return "faq"
        if "summary" in normalized[:500] or "摘要" in text[:500]:
            return "parent_child"
        return "semantic"
