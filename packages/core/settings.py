from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    checkpointer: Literal["memory", "postgres"] = "memory"

    # Phase 1 keys (future phases can consume these
    # without changing the config surface)
    use_mock_llm: bool = True
    mock_mode_strict: bool = False
    openai_api_key: str | None = None
    openai_model_researcher: str = "gpt-4.1"
    openai_model_writer: str = "gpt-4.1-mini"
    openai_model_editor: str = "gpt-4.1-mini"
    api_auth_enabled: bool = False
    api_auth_key: str | None = None
    research_web_search_enabled: bool = True
    research_function_tools_enabled: bool = True

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = (
        "postgresql://postgres:postgres@localhost:5432/research_blog"
    )
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    job_store_backend: Literal["sqlite", "postgres"] = "sqlite"
    job_store_path: str = "./var/jobs.db"

    llm_max_retries: int = 3
    llm_base_backoff_seconds: float = 0.2
    llm_max_backoff_seconds: float = 2.0

    @model_validator(mode="after")
    def validate_llm_mode(self) -> "Settings":
        if not self.use_mock_llm and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when USE_MOCK_LLM is false."
            )
        if self.mock_mode_strict and not self.use_mock_llm:
            raise ValueError(
                "MOCK_MODE_STRICT cannot be true when USE_MOCK_LLM is false."
            )
        if self.api_auth_enabled and not self.api_auth_key:
            raise ValueError(
                "API_AUTH_KEY is required when API_AUTH_ENABLED is true."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
