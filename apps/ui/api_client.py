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
        retry_after_seconds: int | None = None,
        blocked_category: str | None = None,
        reason_codes: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds
        self.blocked_category = blocked_category
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class GenerateResult:
    job_id: str
    status: str
    llm_mode: str


@dataclass(frozen=True)
class StatusResult:
    job_id: str
    topic: str
    llm_mode: str
    max_sources: int
    content_format: str
    content_context: str
    tone: str
    length_preference: str
    research_depth: str
    research_tools_used: list[str]
    status: str
    revision_count: int
    draft: str
    research_notes: list[str]
    editor_feedback: list[str]
    editor_strengths: list[str]
    editor_weaknesses: list[str]
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
        api_auth_enabled: bool = False,
        api_auth_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_auth_enabled = api_auth_enabled
        self.api_auth_key = api_auth_key
        self.session = session or requests.Session()

    def generate(
        self,
        *,
        topic: str,
        llm_mode: str,
        max_sources: int,
        content_format: str,
        content_context: str,
        tone: str,
        length_preference: str,
        research_depth: str,
    ) -> GenerateResult:
        payload = self._request(
            "POST",
            "/generate",
            json={
                "topic": topic,
                "llm_mode": llm_mode,
                "max_sources": max_sources,
                "content_format": content_format,
                "content_context": content_context,
                "tone": tone,
                "length_preference": length_preference,
                "research_depth": research_depth,
            },
        )
        return GenerateResult(
            job_id=str(payload["job_id"]),
            status=str(payload["status"]),
            llm_mode=str(payload.get("llm_mode", "mock")),
        )

    def get_status(self, job_id: str) -> StatusResult:
        payload = self._request("GET", f"/status/{job_id}")
        return StatusResult(
            job_id=str(payload["job_id"]),
            topic=str(payload["topic"]),
            llm_mode=str(payload.get("llm_mode", "mock")),
            max_sources=int(payload.get("max_sources", 6)),
            content_format=str(payload.get("content_format", "Blog article")),
            content_context=str(payload.get("content_context", "")),
            tone=str(payload.get("tone", "professional")),
            length_preference=str(
                payload.get("length_preference", "balanced")
            ),
            research_depth=str(payload.get("research_depth", "standard")),
            research_tools_used=list(payload.get("research_tools_used", [])),
            status=str(payload["status"]),
            revision_count=int(payload["revision_count"]),
            draft=str(payload.get("draft", "")),
            research_notes=list(payload.get("research_notes", [])),
            editor_feedback=list(payload.get("editor_feedback", [])),
            editor_strengths=list(payload.get("editor_strengths", [])),
            editor_weaknesses=list(payload.get("editor_weaknesses", [])),
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
            headers: dict[str, str] = {}
            if self.api_auth_enabled and self.api_auth_key:
                headers["X-API-Key"] = self.api_auth_key
            response = self.session.request(
                method=method,
                url=url,
                json=json,
                headers=headers or None,
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
        retry_after_seconds = detail.get("retry_after_seconds")
        blocked_category = detail.get("blocked_category")
        raw_reason_codes = detail.get("reason_codes")
        reason_codes: list[str] | None = None
        if (
            isinstance(raw_reason_codes, list)
            and all(isinstance(item, str) for item in raw_reason_codes)
        ):
            reason_codes = [str(item) for item in raw_reason_codes]
        message = (
            detail.get("message") or response.text or "API request failed."
        )
        return ApiClientError(
            message,
            status_code=response.status_code,
            error_code=(str(error_code) if error_code is not None else None),
            retry_after_seconds=(
                int(retry_after_seconds)
                if isinstance(retry_after_seconds, int)
                else None
            ),
            blocked_category=(
                str(blocked_category)
                if isinstance(blocked_category, str)
                else None
            ),
            reason_codes=reason_codes,
        )
