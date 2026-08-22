from pathlib import Path

from app.rag.loader import DocumentLoader
from app.rag.parent_child import build_parent_child_from_markdown


def test_parent_child_markdown_builds_parent_and_children(tmp_path: Path) -> None:
    path = tmp_path / "parent_child" / "curry_crab.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        """# 咖喱炒蟹的做法\n\n简介内容。\n\n## 必备原料和工具\n\n- 青蟹\n- 咖喱块\n\n## 计算\n\n每次制作前需要确定计划做几份。\n\n## 操作\n\n- 肉蟹掀盖后对半砍开。\n- 起锅烧油。\n\n## 附加内容\n\n- 做法参考：视频\n""",
        encoding="utf-8",
    )

    document = DocumentLoader().load(path)
    result = build_parent_child_from_markdown(path.name, document)

    assert result.parent.content == "简介内容。"
    assert len(result.children) == 4
    assert result.children[0].content == "## 必备原料和工具\n\n- 青蟹\n- 咖喱块"
    assert result.children[0].metadata["chunk_type"] == "child"
    assert result.children[0].metadata["parent_id"] == result.parent.id


def test_parent_child_markdown_uses_title_as_parent_when_no_intro(tmp_path: Path) -> None:
    path = tmp_path / "parent_child" / "doc.md"
    path.parent.mkdir(parents=True)
    path.write_text("# 文档标题\n\n## 第一部分\n\n正文一。\n\n## 第二部分\n\n正文二。", encoding="utf-8")

    result = build_parent_child_from_markdown(path.name, DocumentLoader().load(path))

    assert result.parent.content == "文档标题"
    assert [child.content for child in result.children] == [
        "## 第一部分\n\n正文一。",
        "## 第二部分\n\n正文二。",
    ]
