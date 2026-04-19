from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./bilancio.db"

    # LLM
    llm_backend: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "gemma34:e2b"
    azure_foundry_endpoint: str = ""
    azure_foundry_api_key: str = ""
    llm_confidence_threshold: float = 0.8

    # File storage
    file_storage_backend: str = "local"
    local_file_dir: str = "./uploads"

    # Observability
    appinsights_connection_string: str = ""

    # Rate limiting
    rate_limit: str = "60/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()