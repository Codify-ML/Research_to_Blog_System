from __future__ import annotations

from time import perf_counter

from fastapi import status

from apps.api.app.schemas import GenerateResponse, StatusResponse
from apps.worker.app.tasks import process_job
from packages.core.errors import QueueUnavailableError


def test_generate_contract_is_async_and_schema_valid(client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-gate-1",
    )

    request_payload = {
        "topic": "Gate check: async generate contract",
        "llm_mode": "mock",
        "max_sources": 7,
        "content_format": "Blog article",
        "content_context": "API readiness validation",
        "tone": "professional",
        "length_preference": "balanced",
        "research_depth": "standard",
    }

    started = perf_counter()
    response = client.post("/generate", json=request_payload)
    elapsed_ms = (perf_counter() - started) * 1000

    assert response.status_code == status.HTTP_200_OK
    parsed = GenerateResponse.model_validate(response.json())
    assert parsed.status.value == "PENDING"
    assert elapsed_ms < 500


def test_status_contract_lifecycle_and_idempotency(client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-gate-2",
    )

    created = client.post(
        "/generate",
        json={"topic": "Gate check: lifecycle and idempotent polling"},
    )
    job_id = created.json()["job_id"]

    process_job(job_id)

    first = client.get(f"/status/{job_id}")
    second = client.get(f"/status/{job_id}")

    assert first.status_code == status.HTTP_200_OK
    assert first.json() == second.json()

    parsed = StatusResponse.model_validate(first.json())
    assert parsed.status.value in {"COMPLETED", "FAILED", "ESCALATED"}

    allowed = {
        "PENDING": {"RUNNING", "FAILED"},
        "RUNNING": {"RETRYING", "COMPLETED", "FAILED", "ESCALATED"},
        "RETRYING": {"RUNNING", "FAILED", "ESCALATED"},
        "COMPLETED": set(),
        "FAILED": set(),
        "ESCALATED": set(),
    }
    transitions = [item["to"] for item in parsed.status_transitions]
    for previous, nxt in zip(transitions, transitions[1:], strict=False):
        assert nxt in allowed[previous]


def test_error_contracts_422_404_503_500(client, monkeypatch):
    validation = client.post("/generate", json={"topic": ""})
    assert validation.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert validation.json()["code"] == "VALIDATION_ERROR"
    assert validation.json()["message"]

    unknown = client.get("/status/unknown-job-id")
    assert unknown.status_code == status.HTTP_404_NOT_FOUND
    assert unknown.json()["code"] == "JOB_NOT_FOUND"
    assert unknown.json()["message"]

    def _raise_queue(_job_id: str) -> str:
        raise QueueUnavailableError("queue down")

    monkeypatch.setattr("apps.api.app.main.enqueue_generate_job", _raise_queue)
    queue_down = client.post(
        "/generate",
        json={"topic": "queue down contract check"},
    )
    assert queue_down.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert queue_down.json()["code"] == "QUEUE_UNAVAILABLE"
    assert queue_down.json()["message"]

    def _raise_unexpected(_job_id: str) -> str:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        _raise_unexpected,
    )
    unexpected = client.post(
        "/generate",
        json={"topic": "unexpected error contract check"},
    )
    assert unexpected.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert unexpected.json()["code"] == "INTERNAL_ERROR"
    assert unexpected.json()["error_id"]
    assert unexpected.json()["timestamp"]
