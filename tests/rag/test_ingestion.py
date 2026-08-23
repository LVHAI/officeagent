from app.rag.ingestion import RAGIngestionPipeline
from app.rag.models import DocumentChunk


class FakeEmbedder:
    def embed_documents_sync(self, texts):
        return [[float(index + 1), 1.0] for index, _ in enumerate(texts)]


def test_ingestion_semantic_chunks_use_embedding_and_persist_vectors():
    class FakeStore:
        def __init__(self):
            self.dimension = None
            self.rows = None

        def reset_collection(self, dimension):
            self.dimension = dimension

        def insert(self, chunks, vectors):
            self.rows = (list(chunks), list(vectors))

    store = FakeStore()
    pipeline = RAGIngestionPipeline(embedder=FakeEmbedder(), vector_store=store)
    chunks = [
        DocumentChunk(id="c1", content="first", metadata={"document": "doc.md", "doc_type": "semantic"}),
        DocumentChunk(id="c2", content="second", metadata={"document": "doc.md", "doc_type": "semantic"}),
    ]

    result = pipeline.persist(chunks)

    assert result == 2
    assert store.dimension == 2
    assert store.rows[1] == [[1.0, 1.0], [2.0, 1.0]]


def test_ingestion_normalizes_required_metadata():
    pipeline = RAGIngestionPipeline(embedder=FakeEmbedder(), vector_store=None)
    chunk = DocumentChunk(id="c1", content="text", metadata={"document": "policy.pdf"})

    normalized = pipeline.normalize_metadata(chunk, department="sales", chapter="refund", page=7)

    assert normalized.metadata["document"] == "policy.pdf"
    assert normalized.metadata["department"] == "sales"
    assert normalized.metadata["chapter"] == "refund"
    assert normalized.metadata["page"] == 7
    assert normalized.metadata["chunk_type"] == "semantic"
