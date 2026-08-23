from app.rag.models import DocumentChunk, RetrievalResult
from app.rag.pipeline import RetrievalPipeline


def test_parent_context_is_restored_for_child_hit():
    parent = DocumentChunk(
        id="parent-1",
        content="文档摘要",
        metadata={"document": "manual.md", "chunk_type": "parent"},
    )
    child = DocumentChunk(
        id="child-1",
        content="具体条款",
        metadata={"document": "manual.md", "chunk_type": "child", "parent_id": "parent-1"},
    )
    results = [RetrievalResult(child, 0.9, "bm25")]

    expanded = RetrievalPipeline.expand_parent_context(results, [parent, child])

    assert [item.chunk.id for item in expanded] == ["child-1", "parent-1"]
    assert expanded[1].route == "parent"
