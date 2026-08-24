import json

from app.agents.aggregator import aggregate_agent_outputs
from app.rag.parent_child import build_parent_child_from_markdown
from app.rag.splitter import policy_nodes


def test_policy_citation_survives_aggregation():
    text = json.dumps([
        {"中华人民共和国劳动合同法 第一条": "为了完善劳动合同制度。"},
        {"中华人民共和国劳动法 第一条": "为了保护劳动者的合法权益。"},
    ], ensure_ascii=False)
    chunks = policy_nodes(text, "劳动法律.json")
    result = aggregate_agent_outputs([
        {
            "agent_id": "knowledge",
            "status": "completed",
            "result": json.dumps({
                "sources": [
                    {
                        "document": chunk.metadata["document"],
                        "article": chunk.metadata["article"],
                        "chunk_id": chunk.id,
                        "document_id": "劳动法律.json",
                        "chunk_type": chunk.metadata["chunk_type"],
                    }
                    for chunk in chunks
                ]
            }, ensure_ascii=False),
            "sources": [],
        }
    ])
    citations = result["sources"]
    assert {item["title"] for item in citations} == {
        "中华人民共和国劳动合同法",
        "中华人民共和国劳动法",
    }
    assert all(item["metadata"]["article"] == "第一条" for item in citations)
    assert all(item["metadata"]["document_id"] == "劳动法律.json" for item in citations)


def test_parent_child_citation_keeps_parent_and_child_identity():
    markdown = """# 咖喱炒蟹的做法

介绍：泰式咖喱炒蟹。

## 必备原料和工具

- 青蟹
- 咖喱块

## 操作

- 煎螃蟹
- 加咖喱和椰浆
"""
    parsed = build_parent_child_from_markdown("咖喱炒蟹.md", markdown)
    child = parsed.children[1]
    result = aggregate_agent_outputs([
        {
            "agent_id": "knowledge",
            "status": "completed",
            "result": json.dumps({
                "sources": [{
                    "document": child.metadata["document"],
                    "chunk_id": child.id,
                    "parent_id": child.metadata["parent_id"],
                    "chunk_type": child.metadata["chunk_type"],
                    "section": "操作",
                }]
            }, ensure_ascii=False),
            "sources": [],
        }
    ])
    citation = result["sources"][0]
    assert citation["title"] == "咖喱炒蟹.md"
    assert citation["metadata"]["chunk_id"] == child.id
    assert citation["metadata"]["parent_id"] == parsed.parent.id
    assert citation["metadata"]["chunk_type"] == "child"
