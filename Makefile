.PHONY: help sync fmt lint test test-unit run-sync

help:
	@echo "Available targets:"
	@echo "  sync      Install/update dependencies with uv"
	@echo "  fmt       Run black formatter"
	@echo "  lint      Run ruff checks"
	@echo "  test      Run unit tests"
	@echo "  test-unit Alias for test"
	@echo "  run-sync  Run the synchronous Phase 1 graph harness"

sync:
	uv sync --all-groups

fmt:
	uv run black .

lint:
	uv run ruff check .

test: test-unit

test-unit:
	uv run pytest tests/unit

run-sync:
	uv run python -m apps.run_phase1_sync "AI agents in production"
