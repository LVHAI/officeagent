from app.rag.parent_child import build_parent_child
from app.rag.splitter import policy_nodes


def test_policy_is_split_by_article():
    chunks = policy_nodes("第三章\n第十二条：A级客户。\n第十三条：特殊折扣。", "sales.pdf")
    assert [chunk.metadata["article"] for chunk in chunks] == ["第十二条", "第十三条"]


def test_parent_child_keeps_parent_reference():
    document = build_parent_child("crm.pdf", "CRM", ["客户画像", "订单历史"])
    assert len(document.children) == 2
    assert all(child.metadata["parent_id"] == document.parent.id for child in document.children)
