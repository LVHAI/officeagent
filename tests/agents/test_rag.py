from app.agents.rag import HybridRetriever, KnowledgeChunk, build_context


def test_hybrid_retriever_returns_ranked_bm25_results_with_source_metadata():
    chunks = [
        KnowledgeChunk("c1", "华东区域销售额下降", "sales.md", page=2, section="华东"),
        KnowledgeChunk("c2", "华南区域销售额增长", "sales.md", page=3, section="华南"),
    ]

    results = HybridRetriever(chunks).retrieve("华东 销售额", top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    assert results[0].document == "sales.md"
    assert results[0].page == 2


def test_context_preserves_citation_metadata():
    context = build_context([KnowledgeChunk("c1", "内容", "policy.pdf", page=7, section="退款")])

    assert "[c1] policy.pdf p.7 / 退款" in context
    assert "内容" in context
