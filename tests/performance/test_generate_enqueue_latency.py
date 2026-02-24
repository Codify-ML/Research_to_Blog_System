from __future__ import annotations

from time import perf_counter

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from packages.core.job_store import get_job_store
from packages.core.settings import get_settings


@pytest.fixture()
def perf_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_STORE_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("JOB_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_MODE_STRICT", "true")

    get_settings.cache_clear()
    get_job_store.cache_clear()

    from apps.api.app.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_job_store.cache_clear()


def _percentile(samples: list[float], percentile: float) -> float:
    assert 0 <= percentile <= 100
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    idx = int(round((percentile / 100.0) * (len(ordered) - 1)))
    return ordered[idx]


def test_generate_enqueue_p95_under_500ms(perf_client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "perf-task-id",
    )

    samples_ms: list[float] = []
    for i in range(80):
        started = perf_counter()
        response = perf_client.post(
            "/generate",
            json={"topic": f"Phase 4.5 perf run {i}"},
        )
        elapsed_ms = (perf_counter() - started) * 1000
        assert response.status_code == status.HTTP_200_OK
        samples_ms.append(elapsed_ms)

    p50 = _percentile(samples_ms, 50)
    p95 = _percentile(samples_ms, 95)
    p99 = _percentile(samples_ms, 99)

    print(
        "POST /generate latency (ms): "
        f"p50={p50:.2f}, p95={p95:.2f}, p99={p99:.2f}"
    )
    assert p95 < 500
