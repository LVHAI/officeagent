from app.rag.query_rewrite import QueryRewriter


def test_query_rewriter_normalizes_whitespace():
    assert QueryRewriter().rewrite("  销售   分析\n  报告 ") == "销售 分析 报告"
