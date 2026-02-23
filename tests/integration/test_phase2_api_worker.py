from __future__ import annotations

from fastapi import status

from apps.worker.app.tasks import process_job
from packages.core.errors import QueueUnavailableError


def test_generate_returns_pending_and_job_id(client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-1",
    )

    response = client.post("/generate", json={"topic": "test topic"})

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "PENDING"
    assert payload["job_id"]


def test_generate_invalid_payload_returns_422(client):
    response = client.post("/generate", json={"topic": ""})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_status_unknown_job_returns_404(client):
    response = client.get("/status/does-not-exist")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"


def test_queue_unavailable_returns_503(client, monkeypatch):
    def _raise_queue_error(_job_id: str) -> str:
        raise QueueUnavailableError("queue down")

    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        _raise_queue_error,
    )

    response = client.post("/generate", json={"topic": "queue test"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"]["code"] == "QUEUE_UNAVAILABLE"


def test_happy_path_lifecycle_and_idempotent_polling(client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-2",
    )

    create_resp = client.post("/generate", json={"topic": "happy path"})
    job_id = create_resp.json()["job_id"]

    process_job(job_id)

    first = client.get(f"/status/{job_id}")
    second = client.get(f"/status/{job_id}")

    assert first.status_code == status.HTTP_200_OK
    assert first.json() == second.json()

    payload = first.json()
    assert payload["status"] == "COMPLETED"
    assert isinstance(payload["research_notes"], list)
    assert payload["research_notes"]

    transitions = payload["status_transitions"]
    transition_targets = [t["to"] for t in transitions]
    assert transition_targets == ["PENDING", "RUNNING", "COMPLETED"]


def test_escalation_path_reaches_terminal_escalated(client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-3",
    )

    response = client.post(
        "/generate",
        json={"topic": "FORCE_ESCALATE deterministic path"},
    )
    job_id = response.json()["job_id"]

    process_job(job_id)

    status_resp = client.get(f"/status/{job_id}")
    payload = status_resp.json()

    assert payload["status"] == "ESCALATED"
    assert payload["revision_count"] == 4


def test_worker_retry_transitions_are_recorded(client, monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        lambda _job_id: "task-4",
    )

    create_resp = client.post("/generate", json={"topic": "retry flow"})
    job_id = create_resp.json()["job_id"]

    call_count = {"count": 0}

    def flaky_workflow(*_args, **_kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("transient failure")
        return {
            "job_id": job_id,
            "topic": "retry flow",
            "research_notes": ["note"],
            "draft": "Draft after retry",
            "editor_feedback": [],
            "is_approved": True,
            "revision_count": 1,
            "status": "COMPLETED",
            "error_message": None,
        }

    class FakeApp:
        def invoke(self, *_args, **_kwargs):
            return flaky_workflow()

    monkeypatch.setattr(
        "apps.worker.app.tasks.create_workflow",
        lambda **_kwargs: FakeApp(),
    )

    process_job(job_id)

    status_resp = client.get(f"/status/{job_id}")
    payload = status_resp.json()

    targets = [item["to"] for item in payload["status_transitions"]]
    assert targets == [
        "PENDING",
        "RUNNING",
        "RETRYING",
        "RUNNING",
        "COMPLETED",
    ]


def test_unexpected_server_error_returns_500_contract(client, monkeypatch):
    def _raise_unexpected(_job_id: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "apps.api.app.main.enqueue_generate_job",
        _raise_unexpected,
    )

    response = client.post("/generate", json={"topic": "boom test"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    payload = response.json()
    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["error_id"]
    assert payload["timestamp"]
