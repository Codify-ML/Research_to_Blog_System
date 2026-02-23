from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from packages.core.job_store import get_job_store
from packages.core.settings import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_STORE_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("JOB_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_MODE_STRICT", "true")
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_BASE_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("LLM_MAX_BACKOFF_SECONDS", "0")

    get_settings.cache_clear()
    get_job_store.cache_clear()

    from apps.api.app.main import create_app

    app = create_app()

    with TestClient(
        app,
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_job_store.cache_clear()
