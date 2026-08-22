from unittest.mock import patch

from app.rag.embedding import EmbeddingService


def test_embedding_service_uses_dashscope_embedding_model_by_default() -> None:
    with patch("app.rag.embedding.OpenAIEmbeddings") as embeddings_cls:
        EmbeddingService()

    kwargs = embeddings_cls.call_args.kwargs
    assert kwargs["model"] == "text-embedding-v4"
    assert kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert kwargs["tiktoken_enabled"] is False
