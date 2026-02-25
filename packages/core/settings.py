from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, model_validator
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
    safety_enabled: bool = True
    safety_fail_closed: bool = False
    safety_profanity_enabled: bool = True
    safety_hate_content_enabled: bool = True
    safety_prompt_injection_enabled: bool = True
    safety_sensitive_data_enabled: bool = True
    safety_openai_moderation_enabled: bool = True
    safety_openai_moderation_model: str = "omni-moderation-latest"
    safety_moderation_score_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
    )

    redis_url: str = "redis://localhost:6379/0"
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "research_blog"
    db_user: str = "postgres"
    db_password: str | None = None
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
        if self.job_store_backend == "postgres":
            _ = self.resolved_database_url
        return self

    @property
    def resolved_database_url(self) -> str:
        if self.database_url and self.database_url.strip():
            return self.database_url

        if not self.db_password:
            raise ValueError(
                "DB_PASSWORD is required when JOB_STORE_BACKEND is postgres "
                "and DATABASE_URL is not set."
            )

        db_user = quote_plus(self.db_user)
        db_password = quote_plus(self.db_password)
        return (
            f"postgresql://{db_user}:{db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
