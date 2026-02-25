from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from packages.core.constants import AgentStatus, LLMMode


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    llm_mode: LLMMode | None = None
    max_sources: int = Field(default=6, ge=1, le=20)
    content_format: str = Field(
        default="Blog article", min_length=3, max_length=120
    )
    content_context: str = Field(default="", max_length=500)
    tone: Literal[
        "professional",
        "humorous",
        "conversational",
        "technical",
        "persuasive",
    ] = "professional"
    length_preference: Literal["short", "balanced", "long"] = "balanced"
    research_depth: Literal["light", "standard", "deep"] = "standard"

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("topic must not be blank")
        return trimmed

    @field_validator("content_format")
    @classmethod
    def content_format_must_not_be_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("content_format must not be blank")
        return trimmed

    @field_validator("content_context")
    @classmethod
    def trim_content_context(cls, value: str) -> str:
        return value.strip()


class GenerateResponse(BaseModel):
    job_id: str
    status: AgentStatus
    llm_mode: LLMMode


class StatusResponse(BaseModel):
    job_id: str
    topic: str
    llm_mode: LLMMode = LLMMode.MOCK
    max_sources: int = 6
    content_format: str = "Blog article"
    content_context: str = ""
    tone: str = "professional"
    length_preference: str = "balanced"
    research_depth: str = "standard"
    research_tools_used: list[str] = Field(default_factory=list)
    status: AgentStatus
    revision_count: int
    draft: str
    research_notes: list[str]
    editor_feedback: list[str]
    editor_strengths: list[str] = Field(default_factory=list)
    editor_weaknesses: list[str] = Field(default_factory=list)
    error_message: str | None
    created_at: str
    updated_at: str
    processing_duration_ms: int | None = None
    status_transitions: list[dict[str, str | None]]


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    error_id: str | None = None
    timestamp: str | None = None
    retry_after_seconds: int | None = None
    blocked_category: str | None = None
    reason_codes: list[str] | None = None
    safety_signals: list[str] | None = None
