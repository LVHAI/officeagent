from pathlib import Path

import pytest

from app.agents.ingestion import DocumentParser, SemanticChunker


def test_markdown_parser_and_semantic_chunker_preserve_section(tmp_path: Path):
    path = tmp_path / "policy.md"
    path.write_text("# 客户管理\n\n第十二条：A级客户享受特殊折扣。\n", encoding="utf-8")

    parsed = DocumentParser().parse(path)
    chunks = SemanticChunker(max_chars=10).chunk(parsed)

    assert chunks
    assert chunks[0].document == "policy.md"
    assert chunks[0].section == "客户管理"
    assert chunks[0].parent_id
    assert "A级客户" in chunks[0].text


def test_parser_rejects_unsupported_document_type(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported document type"):
        DocumentParser().parse(path)
