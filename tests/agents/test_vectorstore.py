from unittest.mock import Mock

from app.agents.vectorstore import MilvusVectorStore, create_milvus_collection_schema


def test_milvus_vector_store_maps_hits_and_metadata():
    hit = Mock()
    hit.entity = {"chunk_id": "c1", "text": "销售下降", "document": "sales.pdf", "page": 3, "section": "销售"}
    hit.distance = 0.91
    collection = Mock()
    collection.search.return_value = [[hit]]

    result = MilvusVectorStore(collection).search([0.1, 0.2], top_k=1)

    assert result[0].chunk_id == "c1"
    assert result[0].page == 3
    collection.search.assert_called_once()


def test_milvus_schema_contains_vector_and_citation_fields():
    names = {field["name"] for field in create_milvus_collection_schema()}
    assert {"chunk_id", "document", "text", "page", "section", "embedding"} <= names
