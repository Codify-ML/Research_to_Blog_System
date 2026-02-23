from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from packages.core.constants import AgentStatus


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("topic must not be blank")
        return trimmed


class GenerateResponse(BaseModel):
    job_id: str
    status: AgentStatus


class StatusResponse(BaseModel):
    job_id: str
    topic: str
    status: AgentStatus
    revision_count: int
    draft: str
    research_notes: list[str]
    editor_feedback: list[str]
    error_message: str | None
    created_at: str
    updated_at: str
    status_transitions: list[dict[str, str | None]]


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    error_id: str | None = None
    timestamp: str | None = None
