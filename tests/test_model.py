import pytest

from app.agents import model
from app.core.config import settings


def test_qwen_is_default_model_configuration():
    assert settings.llm_provider == "qwen"
    assert settings.llm_model == "qwen-plus"
    assert settings.llm_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_qwen_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    with pytest.raises(ValueError, match="LLM_API_KEY is required when LLM_PROVIDER=qwen"):
        model.build_chat_model()


def test_qwen_builds_openai_compatible_client(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(model, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    model.build_chat_model()

    assert captured["model"] == "qwen-plus"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured["max_retries"] == 0
