import json

import pytest

from app.rag.splitter import policy_nodes


def test_policy_json_accepts_chinese_zero_article_number():
    text = json.dumps(
        [
            {
                "中华人民共和国劳动法 第一百零一条": "用人单位无理阻挠劳动行政部门监督检查的，可以依法处理。",
                "中华人民共和国劳动法 第一百零二条": "劳动者违反本法规定的条件解除劳动合同的，应当依法承担责任。",
            }
        ],
        ensure_ascii=False,
    )

    chunks = policy_nodes(text, "劳动法.json")

    assert len(chunks) == 2
    assert chunks[0].metadata["document"] == "中华人民共和国劳动法"
    assert chunks[0].metadata["article"] == "第一百零一条"
    assert chunks[1].metadata["article"] == "第一百零二条"


def test_policy_json_accepts_existing_article_number_forms():
    text = json.dumps(
        [
            {
                "中华人民共和国劳动合同法 第一条": "第一条正文",
                "中华人民共和国劳动合同法 第十条": "第十条正文",
                "中华人民共和国劳动法 第九十九条": "第九十九条正文",
                "中华人民共和国劳动法 第101条": "第一百零一条正文",
            }
        ],
        ensure_ascii=False,
    )

    chunks = policy_nodes(text, "法律.json")

    assert [chunk.metadata["article"] for chunk in chunks] == [
        "第一条",
        "第十条",
        "第九十九条",
        "第101条",
    ]


def test_policy_json_still_rejects_invalid_key():
    text = json.dumps(
        [{"中华人民共和国劳动法": "缺少条款编号"}],
        ensure_ascii=False,
    )

    with pytest.raises(ValueError, match="无效的政策条款 key"):
        policy_nodes(text, "法律.json")
