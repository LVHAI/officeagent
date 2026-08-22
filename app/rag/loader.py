from __future__ import annotations

from pathlib import Path


SUPPORTED_CHUNKING_STRATEGIES = frozenset({"policy", "faq", "parent_child", "semantic"})


class DocumentLoader:
    def load(self, path: str | Path) -> str:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix not in {".txt", ".md"}:
            raise ValueError(f"unsupported document type: {suffix}")
        return file_path.read_text(encoding="utf-8")

    def resolve_type(self, path: str | Path, corpus_root: str | Path | None = None) -> str:
        """Resolve the intended chunking strategy from the corpus folder."""
        file_path = Path(path)
        if corpus_root is not None:
            root = Path(corpus_root).resolve()
            resolved_path = file_path.resolve()
            try:
                relative = resolved_path.relative_to(root)
            except ValueError:
                return DocumentTypeClassifier().classify(file_path.name, self.load(file_path))
            if len(relative.parts) >= 2:
                strategy = relative.parts[0].lower()
                if strategy not in SUPPORTED_CHUNKING_STRATEGIES:
                    raise ValueError(
                        f"unsupported RAG chunking strategy folder: {strategy!r}; "
                        f"expected one of {sorted(SUPPORTED_CHUNKING_STRATEGIES)}"
                    )
                return strategy
        return DocumentTypeClassifier().classify(file_path.name, self.load(file_path))


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
