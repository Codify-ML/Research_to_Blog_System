from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from packages.core.job_store import get_job_store
from packages.core.settings import get_settings


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_STORE_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("JOB_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_MODE_STRICT", "true")
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_AUTH_KEY", "test-api-key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_FAIL_OPEN", "true")

    get_settings.cache_clear()
    get_job_store.cache_clear()

    from apps.api.app.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_job_store.cache_clear()


def test_health_is_public_even_when_api_auth_enabled(auth_client):
    response = auth_client.get("/health")
    assert response.status_code == status.HTTP_200_OK


def test_generate_requires_api_key(auth_client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-auth-1",
    )

    missing = auth_client.post("/generate", json={"topic": "auth check"})
    assert missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert missing.json()["code"] == "UNAUTHORIZED"

    wrong = auth_client.post(
        "/generate",
        json={"topic": "auth check"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert wrong.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong.json()["code"] == "UNAUTHORIZED"

    valid = auth_client.post(
        "/generate",
        json={"topic": "auth check"},
        headers={"X-API-Key": "test-api-key"},
    )
    assert valid.status_code == status.HTTP_200_OK
    assert valid.json()["status"] == "PENDING"


def test_status_requires_api_key(auth_client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-auth-2",
    )

    created = auth_client.post(
        "/generate",
        json={"topic": "status auth check"},
        headers={"X-API-Key": "test-api-key"},
    )
    job_id = created.json()["job_id"]

    missing = auth_client.get(f"/status/{job_id}")
    assert missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert missing.json()["code"] == "UNAUTHORIZED"

    valid = auth_client.get(
        f"/status/{job_id}",
        headers={"X-API-Key": "test-api-key"},
    )
    assert valid.status_code == status.HTTP_200_OK
    assert valid.json()["job_id"] == job_id
