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
- Advanced controls for source cap, tone, length, and research depth
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

### Phase 4 local Docker stack
```bash
make docker-up
make docker-ps
make docker-smoke
make docker-smoke-db
make test-gate
make docker-down
```
`make docker-smoke` executes inside the API container to validate
enqueue/poll lifecycle using the compose network directly.
`make docker-smoke-db` extends this with a direct `psql` check
against Postgres to confirm the corresponding `jobs` row was persisted
with terminal status and transition history.
`make test-gate` runs the Phase 4.5 pre-cloud API readiness suite
(strict API contracts, lifecycle/idempotency checks, reliability checks,
and enqueue latency benchmark with `p95 < 500ms`).
The compose stack uses a Postgres-backed job store (`JOB_STORE_BACKEND=postgres`)
for API/worker parity.

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

When using the Phase 3 UI, each submitted job can override runtime mode:
- `Mock LLM`
- `OpenAI LLM`

Optional strict safety flag:
- `MOCK_MODE_STRICT=true` forces mock-only behavior
  (cannot be combined with `USE_MOCK_LLM=false`).

Researcher tool controls:
- `RESEARCH_WEB_SEARCH_ENABLED=true` enables web search tool availability.
- `RESEARCH_FUNCTION_TOOLS_ENABLED=true` enables function-calling helpers
  for source normalization and scoring.
- Tool usage is still conditional: the researcher only gets tools for
  topics that appear time-sensitive or freshness-dependent.
- For freshness-critical topics (for example `now`, `latest`, market/stock
  prompts), the researcher enforces a recency policy and prefers very recent
  sources.
- UI status now shows `research_tools_used` so you can verify if tools were
  invoked in a run.
- UI exposes `research_depth` (`light`, `standard`, `deep`) to control how
  much breadth/depth the Researcher should produce in notes.

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

## Architecture Reference
- Architecture planning notes are maintained in the local
  `initial_planning/` workspace during planning phases.
