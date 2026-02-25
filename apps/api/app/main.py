from __future__ import annotations

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


def _handle_rate_limit_unavailable(exc: RateLimitUnavailableError) -> None:
    detail = ApiErrorResponse(
        code="RATE_LIMIT_UNAVAILABLE",
        message="Rate limit checks are unavailable. Please retry later.",
    ).model_dump()
    raise HTTPException(status_code=503, detail=detail) from exc


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
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/generate", response_model=GenerateResponse)
    def generate(
        request: GenerateRequest,
        raw_request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> GenerateResponse:
        _enforce_api_auth(provided_api_key=x_api_key)
        store = get_job_store()
        settings = get_settings()
        safety = SafetyService(settings)
        limiter = RateLimitService(settings)
        rate_limit_identity = _rate_limit_identity(
            request=raw_request,
            provided_api_key=x_api_key,
        )

        try:
            cooldown_decision = limiter.check_cooldown(rate_limit_identity)
        except RateLimitUnavailableError as exc:
            _handle_rate_limit_unavailable(exc)
        if cooldown_decision.blocked:
            _raise_rate_limit_response(cooldown_decision)

        try:
            generate_limit_decision = limiter.check_generate(
                rate_limit_identity
            )
        except RateLimitUnavailableError as exc:
            _handle_rate_limit_unavailable(exc)
        if generate_limit_decision.blocked:
            _raise_rate_limit_response(generate_limit_decision)

        selected_mode = request.llm_mode
        if selected_mode is None:
            if settings.use_mock_llm:
                selected_mode = LLMMode.MOCK
            else:
                selected_mode = LLMMode.OPENAI

        if selected_mode == LLMMode.OPENAI and not settings.openai_api_key:
            detail = ApiErrorResponse(
                code="OPENAI_KEY_REQUIRED",
                message=(
                    "OPENAI_API_KEY must be configured to use "
                    "llm_mode='openai'."
                ),
            ).model_dump()
            raise HTTPException(status_code=422, detail=detail)
        if selected_mode == LLMMode.OPENAI and settings.mock_mode_strict:
            detail = ApiErrorResponse(
                code="MOCK_MODE_STRICT",
                message=(
                    "OPENAI mode is disabled while MOCK_MODE_STRICT is true."
                ),
            ).model_dump()
            raise HTTPException(status_code=422, detail=detail)

        try:
            input_decision = safety.classify_input(
                _safety_input_text(request)
            )
        except SafetyUnavailableError as exc:
            detail = ApiErrorResponse(
                code="SAFETY_UNAVAILABLE",
                message="Safety checks are unavailable. Please retry later.",
            ).model_dump()
            raise HTTPException(status_code=503, detail=detail) from exc

        if input_decision.blocked:
            try:
                violation_decision = limiter.record_policy_violation(
                    rate_limit_identity
                )
            except RateLimitUnavailableError as exc:
                _handle_rate_limit_unavailable(exc)
            if violation_decision.blocked:
                _raise_rate_limit_response(violation_decision)

            detail = ApiErrorResponse(
                code="POLICY_BLOCKED_INPUT",
                message=input_decision.message,
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
            raise HTTPException(status_code=503, detail=detail) from exc

        return GenerateResponse(
            job_id=state["job_id"],
            status=AgentStatus.PENDING,
            llm_mode=selected_mode,
        )

    @app.get("/status/{job_id}", response_model=StatusResponse)
    def status(
        job_id: str,
        raw_request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> StatusResponse:
        _enforce_api_auth(provided_api_key=x_api_key)
        settings = get_settings()
        limiter = RateLimitService(settings)
        rate_limit_identity = _rate_limit_identity(
            request=raw_request,
            provided_api_key=x_api_key,
        )

        try:
            status_limit_decision = limiter.check_status(rate_limit_identity)
        except RateLimitUnavailableError as exc:
            _handle_rate_limit_unavailable(exc)
        if status_limit_decision.blocked:
            _raise_rate_limit_response(status_limit_decision)

        store = get_job_store()

        try:
            job = store.get_job_or_raise(job_id)
        except JobNotFoundError as exc:
            detail = ApiErrorResponse(
                code="JOB_NOT_FOUND",
                message=f"job_id '{job_id}' does not exist.",
            ).model_dump()
            raise HTTPException(status_code=404, detail=detail) from exc

        return StatusResponse(**job)

    return app


app = create_app()
