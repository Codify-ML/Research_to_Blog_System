.PHONY: \
	help \
	sync \
	fmt \
	lint \
	test \
	test-unit \
	test-integration \
	run-sync \
	run-api \
	run-worker \
	run-api-bg \
	run-worker-bg \
	run-services-bg \
	debug-openai \
	stop-api \
	stop-worker \
	stop-services

RUN_DIR := .run
API_PID_FILE := $(RUN_DIR)/api.pid
WORKER_PID_FILE := $(RUN_DIR)/worker.pid
API_CMD_PATTERN := uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000
WORKER_CMD_PATTERN := celery -A apps.worker.app.celery_app:celery_app worker -l info

help:
	@echo "Available targets:"
	@echo "  sync      Install/update dependencies with uv"
	@echo "  fmt       Run black formatter"
	@echo "  lint      Run ruff checks"
	@echo "  test      Run unit and integration tests"
	@echo "  test-unit Alias for test"
	@echo "  test-integration Run integration tests"
	@echo "  run-sync  Run the synchronous Phase 1 graph harness"
	@echo "  run-api   Run FastAPI server in foreground (Phase 2)"
	@echo "  run-worker Run Celery worker in foreground (Phase 2)"
	@echo "  run-api-bg Start FastAPI server in background"
	@echo "  run-worker-bg Start Celery worker in background"
	@echo "  run-services-bg Start API and worker in background"
	@echo "  debug-openai Run simple OpenAI connectivity/key check"
	@echo "  stop-api  Stop background API service"
	@echo "  stop-worker Stop background worker service"
	@echo "  stop-services Stop background API and worker services"

sync:
	uv sync --all-groups

fmt:
	uv run black .

lint:
	uv run ruff check .

test: test-unit test-integration

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

run-sync:
	uv run python -m apps.run_phase1_sync "AI agents in production"

run-api:
	uv run uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000

run-worker:
	uv run celery -A apps.worker.app.celery_app:celery_app worker -l info

run-api-bg:
	@mkdir -p $(RUN_DIR)
	@if [ -f $(API_PID_FILE) ] && kill -0 $$(cat $(API_PID_FILE)) 2>/dev/null; then \
		echo "API already running with PID $$(cat $(API_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec uv run $(API_CMD_PATTERN)' \
		> $(RUN_DIR)/api.log 2>&1 & echo $$! > $(API_PID_FILE)
	@echo "API started with PID $$(cat $(API_PID_FILE))"

run-worker-bg:
	@mkdir -p $(RUN_DIR)
	@if [ -f $(WORKER_PID_FILE) ] && kill -0 $$(cat $(WORKER_PID_FILE)) 2>/dev/null; then \
		echo "Worker already running with PID $$(cat $(WORKER_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec uv run $(WORKER_CMD_PATTERN)' \
		> $(RUN_DIR)/worker.log 2>&1 & echo $$! > $(WORKER_PID_FILE)
	@echo "Worker started with PID $$(cat $(WORKER_PID_FILE))"

run-services-bg: run-api-bg run-worker-bg

debug-openai:
	uv run python scripts/debug_openai.py

stop-api:
	@stopped=0; \
	if [ -f $(API_PID_FILE) ]; then \
		PID=$$(cat $(API_PID_FILE)); \
		if kill $$PID >/dev/null 2>&1; then \
			echo "Stopped API service (PID $$PID)"; \
			stopped=1; \
		else \
			echo "API process $$PID was not running"; \
		fi; \
		rm -f $(API_PID_FILE); \
	fi; \
	if command -v pgrep >/dev/null 2>&1; then \
		PIDS=$$(pgrep -f "$(API_CMD_PATTERN)" 2>/dev/null || true); \
	else \
		PIDS=$$(lsof -tiTCP:8000 -sTCP:LISTEN || true); \
	fi; \
	if [ -n "$$PIDS" ]; then \
		kill $$PIDS >/dev/null 2>&1 || true; \
		sleep 1; \
		REMAIN=$$(for p in $$PIDS; do \
			kill -0 $$p 2>/dev/null && printf "%s " $$p; \
		done); \
		if [ -n "$$REMAIN" ]; then \
			kill -CONT $$REMAIN >/dev/null 2>&1 || true; \
			kill $$REMAIN >/dev/null 2>&1 || true; \
			sleep 1; \
		fi; \
		REMAIN=$$(for p in $$PIDS; do \
			kill -0 $$p 2>/dev/null && printf "%s " $$p; \
		done); \
		if [ -n "$$REMAIN" ]; then \
			kill -9 $$REMAIN >/dev/null 2>&1 || true; \
		fi; \
		echo "Stopped API process(es) by pattern: $$PIDS"; \
		stopped=1; \
	fi; \
	if [ $$stopped -eq 0 ]; then \
		echo "No API process found"; \
	fi

stop-worker:
	@stopped=0; \
	if [ -f $(WORKER_PID_FILE) ]; then \
		PID=$$(cat $(WORKER_PID_FILE)); \
		if kill $$PID >/dev/null 2>&1; then \
			echo "Stopped worker service (PID $$PID)"; \
			stopped=1; \
		else \
			echo "Worker process $$PID was not running"; \
		fi; \
		rm -f $(WORKER_PID_FILE); \
	fi; \
	if command -v pgrep >/dev/null 2>&1; then \
		PIDS=$$(pgrep -f "$(WORKER_CMD_PATTERN)" 2>/dev/null || true); \
	else \
		PIDS=""; \
	fi; \
	ACTIVE_PIDS=$$(for p in $$PIDS; do \
		STAT=$$(ps -o stat= -p $$p 2>/dev/null | tr -d ' ' | cut -c1); \
		if [ -n "$$STAT" ] && [ "$$STAT" != "Z" ]; then \
			printf "%s " $$p; \
		fi; \
	done); \
	if [ -n "$$ACTIVE_PIDS" ]; then \
		kill $$ACTIVE_PIDS >/dev/null 2>&1 || true; \
		sleep 1; \
		REMAIN=$$(for p in $$ACTIVE_PIDS; do \
			kill -0 $$p 2>/dev/null && printf "%s " $$p; \
		done); \
		if [ -n "$$REMAIN" ]; then \
			kill -CONT $$REMAIN >/dev/null 2>&1 || true; \
			kill $$REMAIN >/dev/null 2>&1 || true; \
			sleep 1; \
		fi; \
		REMAIN=$$(for p in $$ACTIVE_PIDS; do \
			kill -0 $$p 2>/dev/null && printf "%s " $$p; \
		done); \
		if [ -n "$$REMAIN" ]; then \
			kill -9 $$REMAIN >/dev/null 2>&1 || true; \
		fi; \
		echo "Stopped worker process(es) by pattern: $$ACTIVE_PIDS"; \
		stopped=1; \
	elif [ -n "$$PIDS" ]; then \
		echo "Only defunct worker process(es) found: $$PIDS"; \
		stopped=1; \
	fi; \
	if [ $$stopped -eq 0 ]; then \
		echo "No worker process found"; \
	fi

stop-services: stop-api stop-worker
