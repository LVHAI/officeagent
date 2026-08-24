from app.agents.rag import HybridRetriever, KnowledgeChunk, build_context


def test_hybrid_retrieval_preserves_best_candidate_and_metadata():
    chunks = [
        KnowledgeChunk("a", "A级客户权益 折扣", "policy.pdf", page=12, section="客户管理"),
        KnowledgeChunk("b", "普通客户流程", "faq.md", page=2),
    ]
    result = HybridRetriever(chunks).retrieve("A级客户权益", top_k=1)
    assert result
    assert result[0].chunk_id == "a"
    assert result[0].page == 12


def test_context_builder_keeps_citation_metadata():
    context = build_context(
        [KnowledgeChunk("a", "内容", "policy.pdf", page=12, section="客户管理")]
    )
    assert "policy.pdf p.12 / 客户管理" in context
    assert "[a]" in context
