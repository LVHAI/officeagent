from app.agents.embedding import DeterministicEmbedding
from app.agents.rag import KnowledgeChunk
from app.agents.reranker import KeywordReranker


def test_deterministic_embedding_is_normalized_and_stable():
    model = DeterministicEmbedding(8)
    first = model.embed_query("销售分析")
    second = model.embed_query("销售分析")

    assert first == second
    assert len(first) == 8
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6


def test_reranker_prefers_query_term_overlap():
    chunks = [
        KnowledgeChunk("c1", "销售额 增长", "a.md", score=0.1),
        KnowledgeChunk("c2", "销售额 销售额 下降", "b.md", score=0.1),
    ]

    result = KeywordReranker().rerank("销售额 下降", chunks, top_k=1)

    assert result[0].chunk_id == "c2"
