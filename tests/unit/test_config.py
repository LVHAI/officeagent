from app.core.config import Settings


def test_settings_defaults_for_local_macos_development(monkeypatch):
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("MILVUS_HOST", raising=False)

    settings = Settings(_env_file=None)

    assert settings.postgres_host == "localhost"
    assert settings.redis_host == "localhost"
    assert settings.milvus_host == "localhost"
    assert settings.backend_host == "127.0.0.1"
    assert settings.backend_port == 8000
