from __future__ import annotations

from functools import lru_cache

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


@lru_cache(maxsize=1)
def get_ui_settings() -> UISettings:
    return UISettings()
