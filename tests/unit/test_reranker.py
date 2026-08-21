from app.rag.models import DocumentChunk, RetrievalResult
from app.rag.reranker import Reranker


def test_reranker_prioritizes_exact_query_terms():
    results = [
        RetrievalResult(DocumentChunk("1", "公司销售额增长"), 0.9, "bm25"),
        RetrievalResult(DocumentChunk("2", "公司销售额同比增长 20%"), 0.8, "vector"),
    ]

    ranked = Reranker().rerank("销售额同比增长", results, limit=2)

    assert ranked[0].chunk.id == "2"


def test_reranker_preserves_limit():
    results = [
        RetrievalResult(DocumentChunk(str(i), f"销售报告 {i}"), 1.0 / (i + 1), "bm25")
        for i in range(5)
    ]

    assert len(Reranker().rerank("销售报告", results, limit=2)) == 2
