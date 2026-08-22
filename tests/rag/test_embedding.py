import json

import httpx

from app.core.config import settings
from app.rag.embedding import EmbeddingService


def _service(handler) -> EmbeddingService:
    settings.llm_api_key = "test-key"
    return EmbeddingService(transport=httpx.MockTransport(handler))


def test_dashscope_embedding_sends_raw_strings_not_huggingface_tokens() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [
            {"index": 0, "embedding": [0.1, 0.2], "object": "embedding"},
            {"index": 1, "embedding": [0.3, 0.4], "object": "embedding"},
        ]})

    service = _service(handler)
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
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0], "object": "embedding"}]})

    service = _service(handler)
    vector = service.embed_query_sync("查询内容")

    assert vector == [1.0, 0.0]
    payload = json.loads(requests[0].content)
    assert payload["model"] == "text-embedding-v4"
    assert payload["input"] == ["查询内容"]


def test_dashscope_embedding_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "invalid input", "code": "InvalidParameter"}})

    service = _service(handler)

    try:
        service.embed_documents_sync(["文本"])
    except RuntimeError as exc:
        assert "DashScope embedding request failed" in str(exc)
        assert "InvalidParameter" in str(exc)
    else:
        raise AssertionError("expected DashScope embedding error")
