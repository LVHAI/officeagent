from app.agents.knowledge import create_knowledge_pipeline
from app.agents.rag import KnowledgeChunk


def test_knowledge_pipeline_returns_citation_aware_context():
    pipeline = create_knowledge_pipeline(
        [
            KnowledgeChunk("c1", "退款政策为七天", "policy.pdf", page=4, section="退款"),
            KnowledgeChunk("c2", "发货政策为三天", "shipping.pdf", page=2, section="发货"),
        ]
    )

    result = pipeline.search("退款 政策")

    assert result.chunks
    assert "[c1] policy.pdf p.4 / 退款" in result.context
    assert "退款政策为七天" in result.context
