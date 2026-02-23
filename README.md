# Research to Blog System

Phase 1, Phase 2, and Phase 3 scaffold for a multi-agent content
pipeline.

## Phase 1 Scope
- LangGraph core workflow (Researcher -> Writer -> Editor -> Escalation)
- Deterministic routing guard to prevent infinite revision loops
- Pydantic validation for editor decisions
- Local synchronous run path with MemorySaver
- Unit tests for schema, routing, and workflow behavior

## Phase 2 Scope
- FastAPI async API (`POST /generate`, `GET /status/{job_id}`)
- Celery worker task integration
- SQLite-backed local job store for status lifecycle
- Integration tests for API contracts, lifecycle, retries, and errors

## Phase 3 Scope
- Streamlit UI for topic submission and status polling
- Status panel with lifecycle, notes, feedback, and current draft
- Terminal-state handling for `COMPLETED`, `FAILED`, and `ESCALATED`
- Unit tests for UI API client and status helpers

## Prerequisites
- Python 3.11+
- `uv` installed

## Quickstart
```bash
make sync
make lint
make test
make run-sync
```

### Phase 2 local services
```bash
make run-api
make run-worker
```

### Phase 3 local UI
```bash
make run-ui
```

Ports:
- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:8501`

### Background service control
```bash
make run-services-bg
make run-ui-bg
make stop-services
```

## LLM Mode
The project supports two execution modes for agent LLM calls:
- Mock mode (default): `USE_MOCK_LLM=true`
- Real OpenAI mode: `USE_MOCK_LLM=false` and set `OPENAI_API_KEY`

Optional strict safety flag:
- `MOCK_MODE_STRICT=true` forces mock-only behavior
  (cannot be combined with `USE_MOCK_LLM=false`).

## Key Files
- `packages/core/settings.py`
- `packages/graph/state.py`
- `packages/graph/schemas.py`
- `packages/graph/nodes.py`
- `packages/graph/router.py`
- `packages/graph/workflow.py`
- `apps/run_phase1_sync.py`
- `apps/ui/app.py`
- `apps/ui/api_client.py`
- `tests/unit/`
