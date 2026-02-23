.PHONY: \
	help \
	sync \
	fmt \
	lint \
	test \
	test-unit \
	test-integration \
	test-e2e \
	test-gate \
	test-perf \
	ecr-login-dev \
	image-build-dev \
	image-push-dev \
	deploy-plan-dev \
	deploy-dev \
	tf-fmt \
	tf-init-dev \
	tf-validate-dev \
	tf-plan-dev \
	tf-apply-dev \
	tf-destroy-dev \
	docker-up \
	docker-down \
	docker-logs \
	docker-ps \
	docker-smoke \
	docker-smoke-db \
	docker-smoke-openai \
	run-sync \
	run-api \
	run-worker \
	run-ui \
	run-api-bg \
	run-worker-bg \
	run-ui-bg \
	run-services-bg \
	debug-openai \
	stop-api \
	stop-worker \
	stop-ui \
	stop-services

RUN_DIR := .run
API_PORT := 8000
UI_PORT := 8501
UV_CACHE_DIR := $(RUN_DIR)/uv-cache
UI_HOME := $(abspath $(RUN_DIR)/home)
API_PID_FILE := $(RUN_DIR)/api.pid
WORKER_PID_FILE := $(RUN_DIR)/worker.pid
UI_PID_FILE := $(RUN_DIR)/ui.pid
API_CMD_PATTERN := uvicorn apps.api.app.main:app --host 127.0.0.1 --port $(API_PORT)
WORKER_CMD_PATTERN := celery -A apps.worker.app.celery_app:celery_app worker -l info
UI_CMD_PATTERN := streamlit run apps/ui/app.py --server.address 127.0.0.1 --server.port $(UI_PORT) --browser.gatherUsageStats false --server.headless true
DOCKER_COMPOSE_FILE := docker-compose.local.yml
DOCKER_COMPOSE := docker compose -f $(DOCKER_COMPOSE_FILE)
TF_DEV_DIR := infra/terraform/envs/dev
AWS_PROFILE ?= personal-aws-dev
AWS_REGION ?= us-west-2
AWS_ACCOUNT_ID ?= 497458934978
PROJECT_NAME ?= vc-blog-agent
CLOUD_ENV ?= dev
IMAGE_TAG ?= latest
IMAGE_PLATFORM ?= linux/amd64
ECR_REGISTRY := $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
API_ECR_IMAGE := $(ECR_REGISTRY)/$(PROJECT_NAME)-$(CLOUD_ENV)-api:$(IMAGE_TAG)
WORKER_ECR_IMAGE := $(ECR_REGISTRY)/$(PROJECT_NAME)-$(CLOUD_ENV)-worker:$(IMAGE_TAG)
UI_ECR_IMAGE := $(ECR_REGISTRY)/$(PROJECT_NAME)-$(CLOUD_ENV)-ui:$(IMAGE_TAG)

help:
	@echo "Available targets:"
	@echo "  sync      Install/update dependencies with uv"
	@echo "  fmt       Run black formatter"
	@echo "  lint      Run ruff checks"
	@echo "  test      Run unit and integration tests"
	@echo "  test-unit Alias for test"
	@echo "  test-integration Run integration tests"
	@echo "  test-e2e  Run UI lifecycle e2e tests"
	@echo "  test-gate Run API readiness gate suite (Phase 4.5)"
	@echo "  test-perf Run API enqueue latency benchmark test"
	@echo "  ecr-login-dev Authenticate Docker to dev ECR registry"
	@echo "  image-build-dev Build API/worker/UI images for dev"
	@echo "  image-push-dev Build and push API/worker/UI images to ECR"
	@echo "  deploy-plan-dev Terraform plan for dev using IMAGE_TAG"
	@echo "  deploy-dev Build/push images and apply Terraform with IMAGE_TAG"
	@echo "              Optional IMAGE_PLATFORM (default linux/amd64)"
	@echo "  tf-fmt    Format Terraform files"
	@echo "  tf-init-dev Init Terraform in infra/terraform/envs/dev"
	@echo "  tf-validate-dev Validate Terraform config for dev"
	@echo "  tf-plan-dev Plan Terraform changes for dev"
	@echo "  tf-apply-dev Apply Terraform changes for dev"
	@echo "  tf-destroy-dev Destroy Terraform resources for dev"
	@echo "  docker-up Start local Docker stack (Phase 4)"
	@echo "  docker-down Stop local Docker stack"
	@echo "  docker-logs Tail local Docker stack logs"
	@echo "  docker-ps List local Docker stack service status"
	@echo "  docker-smoke Run API lifecycle smoke against Docker stack"
	@echo "  docker-smoke-db Run smoke + direct Postgres persistence check"
	@echo "  docker-smoke-openai Run OpenAI-backed API smoke in Docker"
	@echo "  run-sync  Run the synchronous Phase 1 graph harness"
	@echo "  run-api   Run FastAPI server in foreground (Phase 2)"
	@echo "  run-worker Run Celery worker in foreground (Phase 2)"
	@echo "  run-ui    Run Streamlit UI in foreground (Phase 3)"
	@echo "  run-api-bg Start FastAPI server in background"
	@echo "  run-worker-bg Start Celery worker in background"
	@echo "  run-ui-bg Start Streamlit UI in background"
	@echo "  run-services-bg Start API, worker, and UI in background"
	@echo "  debug-openai Run simple OpenAI connectivity/key check"
	@echo "  stop-api  Stop background API service"
	@echo "  stop-worker Stop background worker service"
	@echo "  stop-ui   Stop background UI service"
	@echo "  stop-services Stop background API, worker, and UI services"

sync:
	uv sync --all-groups

fmt:
	uv run black .

lint:
	uv run ruff check .

test: test-unit test-integration test-e2e

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

test-e2e:
	uv run pytest tests/e2e

test-gate:
	uv run pytest \
		tests/integration/test_phase2_api_worker.py \
		tests/integration/test_api_readiness_gate.py \
		tests/performance/test_generate_enqueue_latency.py

test-perf:
	uv run pytest tests/performance/test_generate_enqueue_latency.py

ecr-login-dev:
	@AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
		aws ecr get-login-password | docker login \
		--username AWS --password-stdin $(ECR_REGISTRY)

image-build-dev:
	docker build --platform $(IMAGE_PLATFORM) \
		-f docker/api.Dockerfile -t $(API_ECR_IMAGE) .
	docker build --platform $(IMAGE_PLATFORM) \
		-f docker/worker.Dockerfile -t $(WORKER_ECR_IMAGE) .
	docker build --platform $(IMAGE_PLATFORM) \
		-f docker/ui.Dockerfile -t $(UI_ECR_IMAGE) .

image-push-dev: ecr-login-dev image-build-dev
	docker push $(API_ECR_IMAGE)
	docker push $(WORKER_ECR_IMAGE)
	docker push $(UI_ECR_IMAGE)

deploy-plan-dev:
	terraform -chdir=$(TF_DEV_DIR) plan \
		-var-file=terraform.tfvars \
		-var="image_tag=$(IMAGE_TAG)"

deploy-dev: image-push-dev
	terraform -chdir=$(TF_DEV_DIR) apply \
		-var-file=terraform.tfvars \
		-var="image_tag=$(IMAGE_TAG)" \
		-auto-approve

tf-fmt:
	terraform fmt -recursive infra/terraform

tf-init-dev:
	terraform -chdir=$(TF_DEV_DIR) init -reconfigure -backend-config=backend.hcl

tf-validate-dev:
	terraform -chdir=$(TF_DEV_DIR) validate

tf-plan-dev:
	terraform -chdir=$(TF_DEV_DIR) plan -var-file=terraform.tfvars

tf-apply-dev:
	terraform -chdir=$(TF_DEV_DIR) apply -var-file=terraform.tfvars

tf-destroy-dev:
	terraform -chdir=$(TF_DEV_DIR) destroy -var-file=terraform.tfvars

docker-up:
	$(DOCKER_COMPOSE) up --build -d

docker-down:
	$(DOCKER_COMPOSE) down --remove-orphans

docker-logs:
	$(DOCKER_COMPOSE) logs -f --tail=200

docker-ps:
	$(DOCKER_COMPOSE) ps

docker-smoke:
	@$(DOCKER_COMPOSE) exec -T api /bin/sh -lc '\
		resp=$$(curl -sS -X POST http://127.0.0.1:8000/generate \
			-H "content-type: application/json" \
			-d "{\"topic\":\"Docker Phase 4 smoke run\",\"llm_mode\":\"mock\"}"); \
		echo "$$resp"; \
		job_id=$$(python -c "import json,sys; print(json.loads(sys.argv[1])[\"job_id\"])" "$$resp"); \
		for i in $$(seq 1 60); do \
			out=$$(curl -sS "http://127.0.0.1:8000/status/$$job_id"); \
			st=$$(python -c "import json,sys; print(json.loads(sys.argv[1])[\"status\"])" "$$out"); \
			echo "$$st"; \
			if [ "$$st" = "COMPLETED" ] || [ "$$st" = "FAILED" ] || [ "$$st" = "ESCALATED" ]; then \
				echo "$$out"; \
				break; \
			fi; \
			sleep 1; \
		done'

docker-smoke-db:
	@bash scripts/docker_smoke_db_check.sh $(DOCKER_COMPOSE_FILE)

docker-smoke-openai:
	@bash scripts/docker_smoke_openai_check.sh $(DOCKER_COMPOSE_FILE)

run-sync:
	@mkdir -p $(RUN_DIR)
	@env UV_CACHE_DIR=$(UV_CACHE_DIR) \
		uv run python -m apps.run_phase1_sync "AI agents in production"

run-api:
	@mkdir -p $(RUN_DIR)
	@env UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(API_CMD_PATTERN)

run-worker:
	@mkdir -p $(RUN_DIR)
	@env UV_CACHE_DIR=$(UV_CACHE_DIR) \
		uv run celery -A apps.worker.app.celery_app:celery_app worker -l info

run-ui:
	@mkdir -p $(RUN_DIR)
	@mkdir -p $(UI_HOME)
	@env HOME=$(UI_HOME) UV_CACHE_DIR=$(UV_CACHE_DIR) \
		uv run $(UI_CMD_PATTERN)

run-api-bg:
	@mkdir -p $(RUN_DIR)
	@if [ -f $(API_PID_FILE) ] && kill -0 $$(cat $(API_PID_FILE)) 2>/dev/null; then \
		echo "API already running with PID $$(cat $(API_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec env UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(API_CMD_PATTERN)' \
		> $(RUN_DIR)/api.log 2>&1 & echo $$! > $(API_PID_FILE)
	@echo "API started with PID $$(cat $(API_PID_FILE))"

run-worker-bg:
	@mkdir -p $(RUN_DIR)
	@if [ -f $(WORKER_PID_FILE) ] && kill -0 $$(cat $(WORKER_PID_FILE)) 2>/dev/null; then \
		echo "Worker already running with PID $$(cat $(WORKER_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec env UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(WORKER_CMD_PATTERN)' \
		> $(RUN_DIR)/worker.log 2>&1 & echo $$! > $(WORKER_PID_FILE)
	@echo "Worker started with PID $$(cat $(WORKER_PID_FILE))"

run-ui-bg:
	@mkdir -p $(RUN_DIR)
	@mkdir -p $(UI_HOME)
	@if [ -f $(UI_PID_FILE) ] && kill -0 $$(cat $(UI_PID_FILE)) 2>/dev/null; then \
		echo "UI already running with PID $$(cat $(UI_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec env HOME=$(UI_HOME) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(UI_CMD_PATTERN)' \
		> $(RUN_DIR)/ui.log 2>&1 & echo $$! > $(UI_PID_FILE)
	@echo "UI started with PID $$(cat $(UI_PID_FILE))"

run-services-bg: run-api-bg run-worker-bg run-ui-bg

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
		PATTERN_PIDS=$$(pgrep -f "$(API_CMD_PATTERN)" 2>/dev/null || true); \
	else \
		PATTERN_PIDS=""; \
	fi; \
	PORT_PIDS=$$(lsof -tiTCP:$(API_PORT) -sTCP:LISTEN || true); \
	PIDS=$$(printf "%s\n%s\n" "$$PATTERN_PIDS" "$$PORT_PIDS" \
		| tr ' ' '\n' | awk 'NF{seen[$$1]=1} END{for (k in seen) printf "%s ", k}'); \
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
		echo "Stopped worker process(es) by pattern: $$PIDS"; \
		stopped=1; \
	fi; \
	if [ $$stopped -eq 0 ]; then \
		echo "No worker process found"; \
	fi

stop-ui:
	@stopped=0; \
	if [ -f $(UI_PID_FILE) ]; then \
		PID=$$(cat $(UI_PID_FILE)); \
		if kill $$PID >/dev/null 2>&1; then \
			echo "Stopped UI service (PID $$PID)"; \
			stopped=1; \
		else \
			echo "UI process $$PID was not running"; \
		fi; \
		rm -f $(UI_PID_FILE); \
	fi; \
	if command -v pgrep >/dev/null 2>&1; then \
		PATTERN_PIDS=$$(pgrep -f "$(UI_CMD_PATTERN)" 2>/dev/null || true); \
	else \
		PATTERN_PIDS=""; \
	fi; \
	PORT_PIDS=$$(lsof -tiTCP:$(UI_PORT) -sTCP:LISTEN || true); \
	PIDS=$$(printf "%s\n%s\n" "$$PATTERN_PIDS" "$$PORT_PIDS" \
		| tr ' ' '\n' | awk 'NF{seen[$$1]=1} END{for (k in seen) printf "%s ", k}'); \
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
		echo "Stopped UI process(es) by pattern: $$PIDS"; \
		stopped=1; \
	fi; \
	if [ $$stopped -eq 0 ]; then \
		echo "No UI process found"; \
	fi

stop-services: stop-api stop-worker stop-ui
