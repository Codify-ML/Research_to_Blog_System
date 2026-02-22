from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from apps.api.app.queue import enqueue_generate_job
from apps.api.app.schemas import (
    ApiErrorResponse,
    GenerateRequest,
    GenerateResponse,
    StatusResponse,
)
from packages.core.constants import AgentStatus
from packages.core.errors import JobNotFoundError, QueueUnavailableError
from packages.core.job_store import get_job_store
from packages.graph.workflow import initial_state


def create_app() -> FastAPI:
    app = FastAPI(title="Research to Blog API", version="0.2.0")

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
    def generate(request: GenerateRequest) -> GenerateResponse:
        store = get_job_store()

        state = initial_state(request.topic)
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
        )

    @app.get("/status/{job_id}", response_model=StatusResponse)
    def status(job_id: str) -> StatusResponse:
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
