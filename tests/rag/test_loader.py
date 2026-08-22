from pathlib import Path

import pytest

from app.rag.loader import DocumentLoader


def test_resolve_type_uses_explicit_strategy_folder(tmp_path: Path) -> None:
    corpus = tmp_path / "rag"
    for strategy in ("policy", "faq", "parent_child", "semantic"):
        document = corpus / strategy / "example.md"
        document.parent.mkdir(parents=True)
        document.write_text("generic content", encoding="utf-8")
        assert DocumentLoader().resolve_type(document, corpus) == strategy


def test_resolve_type_falls_back_to_content_classifier(tmp_path: Path) -> None:
    corpus = tmp_path / "rag"
    corpus.mkdir()
    document = corpus / "rules.md"
    document.write_text("第一条：适用范围", encoding="utf-8")

    assert DocumentLoader().resolve_type(document, corpus) == "policy"


def test_resolve_type_rejects_unknown_strategy_folder(tmp_path: Path) -> None:
    corpus = tmp_path / "rag"
    document = corpus / "unknown" / "example.md"
    document.parent.mkdir(parents=True)
    document.write_text("generic content", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported RAG chunking strategy folder"):
        DocumentLoader().resolve_type(document, corpus)


def test_resolve_type_works_without_corpus_root(tmp_path: Path) -> None:
    document = tmp_path / "faq.md"
    document.write_text("FAQ: how does this work?", encoding="utf-8")

    assert DocumentLoader().resolve_type(document) == "faq"


def test_load_corpus_reads_all_strategy_folders(tmp_path: Path) -> None:
    corpus = tmp_path / "rag"
    for strategy in ("policy", "faq", "parent_child", "semantic"):
        document = corpus / strategy / f"{strategy}.md"
        document.parent.mkdir(parents=True)
        document.write_text(f"content for {strategy}", encoding="utf-8")

    documents = DocumentLoader().load_corpus(corpus)

    assert {document.doc_type for document in documents} == {
        "policy",
        "faq",
        "parent_child",
        "semantic",
    }
    assert {document.path.parent.name for document in documents} == {
        "policy",
        "faq",
        "parent_child",
        "semantic",
    }
