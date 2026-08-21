from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "officeagent"
    environment: str = "local"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "officeagent"
    postgres_user: str = "officeagent"
    postgres_password: str = "officeagent"

    redis_host: str = "localhost"
    redis_port: int = 6379

    milvus_host: str = "localhost"
    milvus_port: int = 19530

    crm_mcp_url: str = "http://localhost:8101/mcp"
    database_mcp_url: str = "http://localhost:8102/mcp"
    knowledge_mcp_url: str = "http://localhost:8103/mcp"
    report_mcp_url: str = "http://localhost:8104/mcp"

    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
