import json

import httpx

from app.rag.embedding import EmbeddingService


def test_dashscope_embedding_sends_raw_strings_not_huggingface_tokens() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output": {"embeddings": [
            {"text_index": 0, "embedding": [0.1, 0.2]},
            {"text_index": 1, "embedding": [0.3, 0.4]},
        ]}})

    service = EmbeddingService(transport=httpx.MockTransport(handler))
    vectors = service.embed_documents_sync(["第一段。", "第二段。"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    payload = json.loads(requests[0].content)
    assert payload["model"] == "text-embedding-v4"
    assert payload["input"] == ["第一段。", "第二段。"]
    assert all(isinstance(value, str) for value in payload["input"])


def test_dashscope_embedding_query_uses_same_model() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output": {"embeddings": [{"text_index": 0, "embedding": [1.0, 0.0]}]}})

    service = EmbeddingService(transport=httpx.MockTransport(handler))
    vector = service.embed_query_sync("查询内容")

    assert vector == [1.0, 0.0]
    payload = json.loads(requests[0].content)
    assert payload["model"] == "text-embedding-v4"
    assert payload["input"] == ["查询内容"]
