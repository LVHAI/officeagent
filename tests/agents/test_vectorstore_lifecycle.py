from unittest.mock import Mock

from app.agents.vectorstore import MilvusVectorStore


def test_delete_document_removes_all_chunks_for_document():
    collection = Mock()
    store = MilvusVectorStore(collection)

    store.delete_document("manual.md")

    collection.delete.assert_called_once_with(expr='document == "manual.md"')


def test_replace_document_deletes_previous_version_before_insert():
    collection = Mock()
    store = MilvusVectorStore(collection)

    store.replace_document(
        "manual.md",
        [
            {"chunk_id": "c1", "document": "manual.md", "text": "new", "embedding": [0.1, 0.2]},
        ],
    )

    collection.delete.assert_called_once_with(expr='document == "manual.md"')
    collection.insert.assert_called_once()
