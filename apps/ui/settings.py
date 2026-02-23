from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class UISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ui_api_base_url: str = "http://127.0.0.1:8000"
    ui_poll_interval_seconds: float = 1.0
    ui_request_timeout_seconds: float = 10.0
    api_auth_enabled: bool = False
    api_auth_key: str | None = None
    ui_cognito_hosted_ui_base: str = ""
    ui_cognito_client_id: str = ""
    ui_public_base_url: str = "http://127.0.0.1:8501"

    @model_validator(mode="after")
    def validate_api_auth(self) -> UISettings:
        if self.api_auth_enabled and not self.api_auth_key:
            raise ValueError(
                "API_AUTH_KEY is required when API_AUTH_ENABLED is true."
            )
        return self


@lru_cache(maxsize=1)
def get_ui_settings() -> UISettings:
    return UISettings()
