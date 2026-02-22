# Research to Blog System

Phase 1 implementation scaffold for a multi-agent content pipeline.

## Phase 1 Scope
- LangGraph core workflow (Researcher -> Writer -> Editor -> Escalation)
- Deterministic routing guard to prevent infinite revision loops
- Pydantic validation for editor decisions
- Local synchronous run path with MemorySaver
- Unit tests for schema, routing, and workflow behavior

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
- `tests/unit/`
