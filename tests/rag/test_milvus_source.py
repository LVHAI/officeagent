from app.rag.milvus import MilvusRepository


def test_milvus_search_restores_source_metadata(monkeypatch):
    class FakeClient:
        def search(self, **_kwargs):
            return [[
                {
                    "id": "c1",
                    "distance": 0.9,
                    "entity": {
                        "id": "c1",
                        "content": "refund policy",
                        "document": "policy.pdf",
                        "page": 7,
                        "chapter": "refund",
                        "article": "第七条",
                        "department": "sales",
                    },
                }
            ]]

    repo = MilvusRepository.__new__(MilvusRepository)
    repo.collection = "test"
    repo.client = FakeClient()

    result = repo.search([0.1, 0.2])

    assert result[0].chunk.source.document == "policy.pdf"
    assert result[0].chunk.source.page == 7
    assert result[0].chunk.source.section == "refund"
    assert result[0].chunk.source.article == "第七条"
