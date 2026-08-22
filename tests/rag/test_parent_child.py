from pathlib import Path

from app.rag.loader import DocumentLoader
from app.rag.parent_child import build_parent_child_from_markdown


CURRY_CRAB_MARKDOWN = """# 咖喱炒蟹的做法

第一次吃咖喱炒蟹是在泰国的建兴酒家中餐厅，爆肉的螃蟹挂满有蟹黄味道的咖喱，味道真的绝，喜欢吃海鲜的程序员绝对不能错过。操作简单，对沿海的程序员非常友好。

预估烹饪难度：★★★★

## 必备原料和工具

- 青蟹（别称：肉蟹）
- 咖喱块（推介乐惠蟹黄咖喱）
- 洋葱
- 椰浆
- 鸡蛋
- 生粉（别称：淀粉）
- 大蒜

## 计算

每次制作前需要确定计划做几份。一份正好够 1 个人食用

总量：

- 肉蟹 1 只（大约 300g） * 份数
- 咖喱块 15g（一小块）*份数
- 椰浆 100ml*份数
- 鸡蛋 1 个 *份数
- 洋葱 200g *份数
- 大蒜 5 瓣 *份数

## 操作

- 肉蟹掀盖后对半砍开，蟹钳用刀背轻轻拍裂，切口和蟹钳蘸一下生粉，不要太多。撒 5g 生粉到蟹盖中，盖住蟹黄，备用
- 洋葱切成洋葱碎，备用
- 大蒜切碎，备用
- 烧一壶开水，备用
- 起锅烧油，倒入约 20ml 食用油，等待 10 秒让油温升高
- 将螃蟹切口朝下，轻轻放入锅中，煎 20 秒，这一步主要是封住蟹黄，蟹肉。然后翻面，每面煎 10 秒。煎完将螃蟹取出备用
- 将螃蟹盖放入锅中，使用勺子舀起锅中热油泼到蟹盖中，煎封住蟹盖中的蟹黄，煎 20 秒后取出备用
- 不用刷锅，再倒入 10ml 食用油，大火让油温升高至轻微冒烟，将大蒜末，洋葱碎倒入，炒 10 秒钟
- 将咖喱块放入锅中炒化（10 秒），放入煎好的螃蟹，翻炒均匀
- 倒入开水 300ml，焖煮 3 分钟。
- 焖煮完后，倒入椰浆和蛋清，关火，关火后不断翻炒，一直到酱汁变浓稠。
- 出锅

## 附加内容

- 做法参考：[十几年澳门厨房佬教学挂汁的咖喱蟹怎么做](https://www.bilibili.com/video/BV1Nq4y1W7K9)
"""


def test_parent_child_markdown_parses_single_document_by_h2_sections(tmp_path: Path) -> None:
    path = tmp_path / "parent_child" / "curry_crab.md"
    path.parent.mkdir(parents=True)
    path.write_text(CURRY_CRAB_MARKDOWN, encoding="utf-8")

    document = DocumentLoader().load(path)
    result = build_parent_child_from_markdown(path.name, document)

    assert result.parent.content == (
        "第一次吃咖喱炒蟹是在泰国的建兴酒家中餐厅，爆肉的螃蟹挂满有蟹黄味道的咖喱，"
        "味道真的绝，喜欢吃海鲜的程序员绝对不能错过。操作简单，对沿海的程序员非常友好。\n\n"
        "预估烹饪难度：★★★★"
    )
    assert len(result.children) == 4
    assert result.children[0].content == "## 必备原料和工具\n\n- 青蟹（别称：肉蟹）\n- 咖喱块（推介乐惠蟹黄咖喱）\n- 洋葱\n- 椰浆\n- 鸡蛋\n- 生粉（别称：淀粉）\n- 大蒜"
    assert result.children[1].content.startswith("## 计算\n\n")
    assert result.children[2].content.startswith("## 操作\n\n")
    assert result.children[3].content.startswith("## 附加内容\n\n")

    parent_id = result.parent.id
    assert result.parent.metadata["chunk_type"] == "parent"
    assert all(child.metadata["chunk_type"] == "child" for child in result.children)
    assert all(child.metadata["parent_id"] == parent_id for child in result.children)


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
