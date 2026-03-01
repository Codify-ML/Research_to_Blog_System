from __future__ import annotations

import time
from datetime import UTC, datetime
from hmac import compare_digest
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.api.app.queue import enqueue_generate_job
from apps.api.app.schemas import (
    ApiErrorResponse,
    GenerateRequest,
    GenerateResponse,
    StatusResponse,
)
from packages.core.constants import AgentStatus, LLMMode
from packages.core.errors import (
    JobNotFoundError,
    QueueUnavailableError,
    RateLimitUnavailableError,
    SafetyUnavailableError,
)
from packages.core.job_store import get_job_store
from packages.core.observability import get_observability, update_span
from packages.core.rate_limit import (
    RateLimitDecision,
    RateLimitService,
    build_rate_limit_identity,
)
from packages.core.safety import SafetyService
from packages.core.settings import get_settings
from packages.graph.workflow import initial_state


def _enforce_api_auth(
    *,
    provided_api_key: str | None,
) -> None:
    settings = get_settings()
    if not settings.api_auth_enabled:
        return

    expected_key = settings.api_auth_key
    if (
        expected_key is None
        or provided_api_key is None
        or not compare_digest(provided_api_key, expected_key)
    ):
        detail = ApiErrorResponse(
            code="UNAUTHORIZED",
            message="Valid API key is required.",
        ).model_dump()
        raise HTTPException(status_code=401, detail=detail)


def _safety_input_text(request: GenerateRequest) -> str:
    return "\n".join(
        part
        for part in (
            request.topic,
            request.content_context,
            request.content_format,
        )
        if part
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", maxsplit=1)[0].strip()
        if first:
            return first
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_identity(
    *,
    request: Request,
    provided_api_key: str | None,
) -> str:
    return build_rate_limit_identity(
        api_key=provided_api_key,
        client_ip=_client_ip(request),
    )


def _raise_rate_limit_response(decision: RateLimitDecision) -> None:
    detail = ApiErrorResponse(
        code=decision.code or "RATE_LIMITED",
        message=decision.message or "Rate limit exceeded.",
        retry_after_seconds=decision.retry_after_seconds,
    ).model_dump()
    raise HTTPException(status_code=429, detail=detail)


def _blocked_category_from_reason_codes(
    reason_codes: list[str],
) -> str | None:
    upper_codes = {code.upper() for code in reason_codes}
    if any(
        code == "SAFETY_HATE_CONTENT" or code.startswith("SAFETY_HATE")
        for code in upper_codes
    ):
        return "hate_content"
    if "SAFETY_PROMPT_INJECTION" in upper_codes:
        return "prompt_injection"
    if "SAFETY_SENSITIVE_DATA" in upper_codes:
        return "sensitive_data"
    if "SAFETY_PROFANITY" in upper_codes:
        return "profanity"
    if any(code.startswith("SAFETY_") for code in upper_codes):
        return "moderation"
    return None


def _handle_rate_limit_unavailable(exc: RateLimitUnavailableError) -> None:
    detail = ApiErrorResponse(
        code="RATE_LIMIT_UNAVAILABLE",
        message="Rate limit checks are unavailable. Please retry later.",
    ).model_dump()
    raise HTTPException(status_code=503, detail=detail) from exc


def _capture_content_enabled() -> bool:
    return get_settings().langfuse_capture_content


def _as_observability_payload(
    payload: dict[str, object],
) -> dict[str, object] | None:
    if not _capture_content_enabled():
        return None
    return payload


def _health_check_payload() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "job_store_backend": settings.job_store_backend,
        "rate_limit_enabled": str(settings.rate_limit_enabled).lower(),
        "safety_enabled": str(settings.safety_enabled).lower(),
        "langfuse_enabled": str(settings.langfuse_enabled).lower(),
    }


def _readiness_payload() -> tuple[dict[str, object], int]:
    settings = get_settings()
    checks: dict[str, str] = {}
    status_code = 200

    try:
        _ = get_job_store()
        checks["job_store"] = "ok"
    except Exception:
        checks["job_store"] = "error"
        status_code = 503

    limiter_ok = RateLimitService(settings).backend_available()
    if settings.rate_limit_enabled:
        checks["rate_limit_redis"] = "ok" if limiter_ok else "error"
        if not limiter_ok and not settings.rate_limit_fail_open:
            status_code = 503
    else:
        checks["rate_limit_redis"] = "disabled"

    if settings.safety_openai_moderation_enabled:
        checks["safety_moderation_config"] = (
            "ok" if bool(settings.openai_api_key) else "missing_openai_key"
        )
        if settings.safety_fail_closed and not settings.openai_api_key:
            status_code = 503
    else:
        checks["safety_moderation_config"] = "disabled"

    status_text = "ready" if status_code == 200 else "not_ready"
    payload: dict[str, object] = {
        "status": status_text,
        "checks": checks,
    }
    return payload, status_code


def _readiness_response(*, endpoint_path: str) -> JSONResponse:
    settings = get_settings()
    observability = get_observability(settings)
    started = time.perf_counter()
    payload, status_code = _readiness_payload()
    if not settings.langfuse_trace_health_endpoints:
        return JSONResponse(status_code=status_code, content=payload)

    with observability.span(
        name="api.readiness",
        metadata={"endpoint": endpoint_path},
    ) as span:
        duration_ms = int((time.perf_counter() - started) * 1000)
        update_span(
            span,
            output_payload=_as_observability_payload(payload),
            metadata={
                "duration_ms": duration_ms,
                "status": str(payload["status"]),
                "http_status": status_code,
            },
            level="ERROR" if status_code >= 500 else None,
        )
        observability.flush()
        return JSONResponse(status_code=status_code, content=payload)


def create_app() -> FastAPI:
    app = FastAPI(title="Research to Blog API", version="0.2.0")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, _exc):
        payload = ApiErrorResponse(
            code="VALIDATION_ERROR",
            message="Invalid request payload.",
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code")
            message = exc.detail.get("message")
            retry_after_seconds = exc.detail.get("retry_after_seconds")
            blocked_category = exc.detail.get("blocked_category")
            raw_reason_codes = exc.detail.get("reason_codes")
            raw_safety_signals = exc.detail.get("safety_signals")
            reason_codes: list[str] | None = None
            if (
                isinstance(raw_reason_codes, list)
                and all(isinstance(item, str) for item in raw_reason_codes)
            ):
                reason_codes = [str(item) for item in raw_reason_codes]
            safety_signals: list[str] | None = None
            if (
                isinstance(raw_safety_signals, list)
                and all(
                    isinstance(item, str) for item in raw_safety_signals
                )
            ):
                safety_signals = [
                    str(item)
                    for item in raw_safety_signals
                ]
            if (
                isinstance(code, str)
                and isinstance(message, str)
                and (
                    retry_after_seconds is None
                    or isinstance(retry_after_seconds, int)
                )
            ):
                payload = ApiErrorResponse(
                    code=code,
                    message=message,
                    retry_after_seconds=retry_after_seconds,
                    blocked_category=(
                        blocked_category
                        if isinstance(blocked_category, str)
                        else None
                    ),
                    reason_codes=reason_codes,
                    safety_signals=safety_signals,
                )
                return JSONResponse(
                    status_code=exc.status_code,
                    content=payload.model_dump(),
                )

        payload = ApiErrorResponse(
            code="HTTP_ERROR",
            message=str(exc.detail),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request, _exc):
        error_id = str(uuid4())
        payload = ApiErrorResponse(
            code="INTERNAL_ERROR",
            message="Unexpected server error.",
            error_id=error_id,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    @app.get("/health")
    def health() -> dict[str, str]:
        settings = get_settings()
        observability = get_observability(settings)
        started = time.perf_counter()
        payload = _health_check_payload()
        if not settings.langfuse_trace_health_endpoints:
            return payload

        with observability.span(
            name="api.health",
            metadata={"endpoint": "/health"},
        ) as span:
            duration_ms = int((time.perf_counter() - started) * 1000)
            update_span(
                span,
                output_payload=_as_observability_payload(payload),
                metadata={"duration_ms": duration_ms, "status": "ok"},
            )
            observability.flush()
            return payload

    @app.get("/ready")
    @app.get("/readiness")
    def readiness(request: Request) -> JSONResponse:
        return _readiness_response(endpoint_path=request.url.path)

    @app.post("/generate", response_model=GenerateResponse)
    def generate(
        request: GenerateRequest,
        raw_request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> GenerateResponse:
        _enforce_api_auth(provided_api_key=x_api_key)
        store = get_job_store()
        settings = get_settings()
        observability = get_observability(settings)
        safety = SafetyService(settings)
        limiter = RateLimitService(settings)
        rate_limit_identity = _rate_limit_identity(
            request=raw_request,
            provided_api_key=x_api_key,
        )
        with observability.span(
            name="api.generate",
            input_payload=_as_observability_payload(
                request.model_dump(mode="json")
            ),
            metadata={
                "client_ip": _client_ip(raw_request),
                "llm_mode_requested": (
                    request.llm_mode.value
                    if request.llm_mode is not None
                    else "default"
                ),
                "max_sources": request.max_sources,
            },
        ) as span:

            try:
                cooldown_decision = limiter.check_cooldown(
                    rate_limit_identity
                )
            except RateLimitUnavailableError as exc:
                update_span(
                    span,
                    metadata={"rate_limit_unavailable": True},
                    level="ERROR",
                    status_message=str(exc),
                )
                _handle_rate_limit_unavailable(exc)
            if cooldown_decision.blocked:
                update_span(
                    span,
                    metadata={
                        "rate_limit_blocked": True,
                        "rate_limit_code": cooldown_decision.code,
                    },
                    level="WARNING",
                    status_message=cooldown_decision.message,
                )
                _raise_rate_limit_response(cooldown_decision)

            try:
                generate_limit_decision = limiter.check_generate(
                    rate_limit_identity
                )
            except RateLimitUnavailableError as exc:
                update_span(
                    span,
                    metadata={"rate_limit_unavailable": True},
                    level="ERROR",
                    status_message=str(exc),
                )
                _handle_rate_limit_unavailable(exc)
            if generate_limit_decision.blocked:
                update_span(
                    span,
                    metadata={
                        "rate_limit_blocked": True,
                        "rate_limit_code": generate_limit_decision.code,
                    },
                    level="WARNING",
                    status_message=generate_limit_decision.message,
                )
                _raise_rate_limit_response(generate_limit_decision)

            selected_mode = request.llm_mode
            if selected_mode is None:
                if settings.use_mock_llm:
                    selected_mode = LLMMode.MOCK
                else:
                    selected_mode = LLMMode.OPENAI

            if selected_mode == LLMMode.OPENAI and settings.mock_mode_strict:
                detail = ApiErrorResponse(
                    code="MOCK_MODE_STRICT",
                    message=(
                        "OPENAI mode is disabled while MOCK_MODE_STRICT is "
                        "true."
                    ),
                ).model_dump()
                update_span(
                    span,
                    metadata={"llm_mode_rejected": LLMMode.OPENAI.value},
                    level="WARNING",
                    status_message=str(detail["message"]),
                )
                raise HTTPException(status_code=422, detail=detail)
            if selected_mode == LLMMode.OPENAI and not settings.openai_api_key:
                detail = ApiErrorResponse(
                    code="OPENAI_KEY_REQUIRED",
                    message=(
                        "OPENAI_API_KEY must be configured to use "
                        "llm_mode='openai'."
                    ),
                ).model_dump()
                update_span(
                    span,
                    metadata={"llm_mode_rejected": LLMMode.OPENAI.value},
                    level="WARNING",
                    status_message=str(detail["message"]),
                )
                raise HTTPException(status_code=422, detail=detail)

            try:
                input_decision = safety.classify_input(
                    _safety_input_text(request)
                )
            except SafetyUnavailableError as exc:
                detail = ApiErrorResponse(
                    code="SAFETY_UNAVAILABLE",
                    message=(
                        "Safety checks are unavailable. Please retry later."
                    ),
                ).model_dump()
                update_span(
                    span,
                    metadata={"guardrail_unavailable": True},
                    level="ERROR",
                    status_message=str(detail["message"]),
                )
                raise HTTPException(status_code=503, detail=detail) from exc

            if input_decision.blocked:
                update_span(
                    span,
                    output_payload=_as_observability_payload(
                        {
                            "guardrail_response": input_decision.message,
                            "reason_codes": input_decision.reason_codes,
                            "signals": input_decision.signals,
                        }
                    ),
                    metadata={
                        "guardrail_blocked_input": True,
                        "reason_codes": input_decision.reason_codes,
                    },
                    level="WARNING",
                    status_message=input_decision.message,
                )
                try:
                    violation_decision = limiter.record_policy_violation(
                        rate_limit_identity
                    )
                except RateLimitUnavailableError as exc:
                    update_span(
                        span,
                        metadata={"rate_limit_unavailable": True},
                        level="ERROR",
                        status_message=str(exc),
                    )
                    _handle_rate_limit_unavailable(exc)
                if violation_decision.blocked:
                    update_span(
                        span,
                        metadata={
                            "rate_limit_blocked": True,
                            "rate_limit_code": violation_decision.code,
                        },
                        level="WARNING",
                        status_message=violation_decision.message,
                    )
                    _raise_rate_limit_response(violation_decision)

                detail = ApiErrorResponse(
                    code="POLICY_BLOCKED_INPUT",
                    message=input_decision.message,
                    blocked_category=_blocked_category_from_reason_codes(
                        input_decision.reason_codes
                    ),
                    reason_codes=input_decision.reason_codes,
                    safety_signals=(
                        input_decision.signals
                        if settings.safety_explain_enabled
                        else None
                    ),
                ).model_dump()
                raise HTTPException(status_code=422, detail=detail)

            state = initial_state(
                request.topic,
                llm_mode=selected_mode,
                max_sources=request.max_sources,
                content_format=request.content_format,
                content_context=request.content_context,
                tone=request.tone,
                length_preference=request.length_preference,
                research_depth=request.research_depth,
            )
            store.create_job(state)

            try:
                enqueue_generate_job(state["job_id"])
            except QueueUnavailableError as exc:
                store.set_status(
                    job_id=state["job_id"],
                    next_status=AgentStatus.FAILED,
                    error_message=str(exc),
                )
                detail = ApiErrorResponse(
                    code="QUEUE_UNAVAILABLE",
                    message="Queue is unavailable. Please retry later.",
                ).model_dump()
                update_span(
                    span,
                    metadata={"queue_unavailable": True},
                    level="ERROR",
                    status_message=str(detail["message"]),
                )
                raise HTTPException(status_code=503, detail=detail) from exc

            response_payload = GenerateResponse(
                job_id=state["job_id"],
                status=AgentStatus.PENDING,
                llm_mode=selected_mode,
            )
            update_span(
                span,
                output_payload=_as_observability_payload(
                    response_payload.model_dump(mode="json")
                ),
                metadata={
                    "job_id": state["job_id"],
                    "llm_mode": selected_mode.value,
                },
            )
            observability.flush()
            return response_payload

    @app.get("/status/{job_id}", response_model=StatusResponse)
    def status(
        job_id: str,
        raw_request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> StatusResponse:
        _enforce_api_auth(provided_api_key=x_api_key)
        settings = get_settings()
        observability = get_observability(settings)
        limiter = RateLimitService(settings)
        rate_limit_identity = _rate_limit_identity(
            request=raw_request,
            provided_api_key=x_api_key,
        )
        with observability.span(
            name="api.status",
            metadata={
                "client_ip": _client_ip(raw_request),
                "job_id": job_id,
            },
        ) as span:

            try:
                status_limit_decision = limiter.check_status(
                    rate_limit_identity
                )
            except RateLimitUnavailableError as exc:
                update_span(
                    span,
                    metadata={"rate_limit_unavailable": True},
                    level="ERROR",
                    status_message=str(exc),
                )
                _handle_rate_limit_unavailable(exc)
            if status_limit_decision.blocked:
                update_span(
                    span,
                    metadata={
                        "rate_limit_blocked": True,
                        "rate_limit_code": status_limit_decision.code,
                    },
                    level="WARNING",
                    status_message=status_limit_decision.message,
                )
                _raise_rate_limit_response(status_limit_decision)

            store = get_job_store()

            try:
                job = store.get_job_or_raise(job_id)
            except JobNotFoundError as exc:
                detail = ApiErrorResponse(
                    code="JOB_NOT_FOUND",
                    message=f"job_id '{job_id}' does not exist.",
                ).model_dump()
                update_span(
                    span,
                    metadata={"job_found": False},
                    level="WARNING",
                    status_message=str(detail["message"]),
                )
                raise HTTPException(status_code=404, detail=detail) from exc

            response_payload = StatusResponse(**job)
            is_terminal = response_payload.status in {
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
                AgentStatus.ESCALATED,
            }
            update_span(
                span,
                output_payload=(
                    _as_observability_payload(
                        response_payload.model_dump(mode="json")
                    )
                    if is_terminal
                    else None
                ),
                metadata={
                    "status": str(response_payload.status.value),
                    "terminal": is_terminal,
                    "revision_count": response_payload.revision_count,
                },
            )
            observability.flush()
            return response_payload

    return app


app = create_app()
