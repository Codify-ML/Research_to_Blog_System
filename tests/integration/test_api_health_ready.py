from __future__ import annotations

from fastapi import status


def test_health_contract(client) -> None:
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "ok"


def test_ready_contract(client) -> None:
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "ready"
    assert isinstance(payload["checks"], dict)
