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

    # Use IPv4 explicitly for local Docker-published ports. On macOS,
    # localhost may resolve to ::1 first while Docker Desktop's published
    # port is served through IPv4, causing connection resets during MCP
    # discovery.
    crm_mcp_url: str = "http://127.0.0.1:8101/mcp"
    database_mcp_url: str = "http://127.0.0.1:8102/mcp"
    knowledge_mcp_url: str = "http://127.0.0.1:8103/mcp"
    report_mcp_url: str = "http://127.0.0.1:8104/mcp"

    # Qwen is the platform's default LLM. It is accessed through
    # Alibaba Cloud Model Studio's OpenAI-compatible Chat Completions API.
    llm_provider: str = "qwen"
    llm_api_key: str | None = None
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: float = 60.0
    embedding_model: str = "text-embedding-3-small"
    tavily_api_key: str | None = None

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
