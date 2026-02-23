from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ESCALATED"}


class ApiClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class GenerateResult:
    job_id: str
    status: str


@dataclass(frozen=True)
class StatusResult:
    job_id: str
    topic: str
    status: str
    revision_count: int
    draft: str
    research_notes: list[str]
    editor_feedback: list[str]
    error_message: str | None
    updated_at: str

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


class ApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def generate(self, topic: str) -> GenerateResult:
        payload = self._request("POST", "/generate", json={"topic": topic})
        return GenerateResult(
            job_id=str(payload["job_id"]),
            status=str(payload["status"]),
        )

    def get_status(self, job_id: str) -> StatusResult:
        payload = self._request("GET", f"/status/{job_id}")
        return StatusResult(
            job_id=str(payload["job_id"]),
            topic=str(payload["topic"]),
            status=str(payload["status"]),
            revision_count=int(payload["revision_count"]),
            draft=str(payload.get("draft", "")),
            research_notes=list(payload.get("research_notes", [])),
            editor_feedback=list(payload.get("editor_feedback", [])),
            error_message=payload.get("error_message"),
            updated_at=str(payload["updated_at"]),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ApiClientError(
                f"Request to API failed: {exc}",
            ) from exc

        if response.ok:
            data = response.json()
            if not isinstance(data, dict):
                raise ApiClientError("API returned non-object JSON response.")
            return data

        raise self._build_api_error(response)

    def _build_api_error(self, response: requests.Response) -> ApiClientError:
        detail: dict[str, Any] = {}
        try:
            payload = response.json()
            if isinstance(payload, dict):
                raw_detail = payload.get("detail", payload)
                if isinstance(raw_detail, dict):
                    detail = raw_detail
        except ValueError:
            detail = {}

        error_code = detail.get("code")
        message = (
            detail.get("message") or response.text or "API request failed."
        )
        return ApiClientError(
            message,
            status_code=response.status_code,
            error_code=(str(error_code) if error_code is not None else None),
        )
