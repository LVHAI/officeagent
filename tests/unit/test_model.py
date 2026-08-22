from app.agents.model import build_chat_model


def test_build_chat_model_uses_bounded_network_timeout(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.agents.model.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.agents.model.settings.llm_model", "test-model")
    monkeypatch.setattr("app.agents.model.settings.llm_timeout_seconds", 12.5)
    monkeypatch.setattr("app.agents.model.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.agents.model.settings.llm_base_url", "http://llm.test/v1")

    build_chat_model()

    assert captured["model"] == "test-model"
    assert captured["timeout"] == 12.5
    assert captured["max_retries"] == 0
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "http://llm.test/v1"
