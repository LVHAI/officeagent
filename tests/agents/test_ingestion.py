from pathlib import Path

from app.agents.ingestion import DocumentParser, SemanticChunker


def test_markdown_parser_and_parent_child_chunking(tmp_path: Path):
    path = tmp_path / "policy.md"
    path.write_text("# 退款\n退款政策七天。\n\n## 例外\n特殊商品除外。", encoding="utf-8")

    parsed = DocumentParser().parse(path)
    chunks = SemanticChunker(max_chars=20).chunk(parsed)

    assert chunks
    assert chunks[0].document == "policy.md"
    assert chunks[0].parent_id
    assert any(chunk.section == "例外" for chunk in chunks)
