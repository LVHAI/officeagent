from __future__ import annotations

from pathlib import Path


class DocumentLoader:
    def load(self, path: str | Path) -> str:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix not in {".txt", ".md"}:
            raise ValueError(f"unsupported document type: {suffix}")
        return file_path.read_text(encoding="utf-8")


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
