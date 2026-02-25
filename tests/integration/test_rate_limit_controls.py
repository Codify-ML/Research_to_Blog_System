from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from packages.core.job_store import get_job_store
from packages.core.rate_limit import RateLimitDecision
from packages.core.settings import get_settings
from packages.graph.workflow import initial_state


@pytest.fixture()
def rate_limited_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_STORE_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("JOB_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_MODE_STRICT", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_FAIL_OPEN", "true")
    monkeypatch.setenv("SAFETY_OPENAI_MODERATION_ENABLED", "false")
    monkeypatch.setenv("SAFETY_FAIL_CLOSED", "false")

    get_settings.cache_clear()
    get_job_store.cache_clear()

    from apps.api.app.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_job_store.cache_clear()


def test_generate_returns_429_when_rate_limited(
    rate_limited_client,
    monkeypatch,
):
    class _Limiter:
        def __init__(self, _settings):
            pass

        def check_cooldown(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def check_generate(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision(
                blocked=True,
                code="RATE_LIMITED",
                message="Too many generate requests.",
                retry_after_seconds=42,
            )

        def check_status(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def record_policy_violation(
            self,
            _identity: str,
        ) -> RateLimitDecision:
            return RateLimitDecision.allow()

    monkeypatch.setattr("apps.api.app.main.RateLimitService", _Limiter)

    response = rate_limited_client.post(
        "/generate",
        json={"topic": "rate limit test"},
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    payload = response.json()
    assert payload["code"] == "RATE_LIMITED"
    assert payload["retry_after_seconds"] == 42


def test_status_returns_429_when_rate_limited(
    rate_limited_client,
    monkeypatch,
):
    class _Limiter:
        def __init__(self, _settings):
            pass

        def check_cooldown(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def check_generate(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def check_status(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision(
                blocked=True,
                code="RATE_LIMITED",
                message="Too many status requests.",
                retry_after_seconds=7,
            )

        def record_policy_violation(
            self,
            _identity: str,
        ) -> RateLimitDecision:
            return RateLimitDecision.allow()

    monkeypatch.setattr("apps.api.app.main.RateLimitService", _Limiter)

    store = get_job_store()
    state = initial_state("status limit test")
    store.create_job(state)

    response = rate_limited_client.get(f"/status/{state['job_id']}")

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    payload = response.json()
    assert payload["code"] == "RATE_LIMITED"
    assert payload["retry_after_seconds"] == 7


def test_policy_abuse_triggers_429_cooldown(
    rate_limited_client,
    monkeypatch,
):
    class _Limiter:
        def __init__(self, _settings):
            pass

        def check_cooldown(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def check_generate(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def check_status(self, _identity: str) -> RateLimitDecision:
            return RateLimitDecision.allow()

        def record_policy_violation(
            self,
            _identity: str,
        ) -> RateLimitDecision:
            return RateLimitDecision(
                blocked=True,
                code="ABUSE_COOLDOWN",
                message="Cooldown active.",
                retry_after_seconds=900,
            )

    monkeypatch.setattr("apps.api.app.main.RateLimitService", _Limiter)

    response = rate_limited_client.post(
        "/generate",
        json={"topic": "Write a fucking hateful post."},
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    payload = response.json()
    assert payload["code"] == "ABUSE_COOLDOWN"
    assert payload["retry_after_seconds"] == 900
