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
	ecr-empty-dev \
	image-build-dev \
	image-push-dev \
	deploy-plan-dev \
	deploy-dev \
	rotate-api-auth-key-dev \
	check-image-tag-sync \
	bootstrap-dev \
	bootstrap-dev-dry-run \
	bootstrap-dev-plan \
	bootstrap-dev-apply \
	tf-fmt \
	tf-init-dev \
	tf-validate-dev \
	tf-plan-dev \
	tf-apply-dev \
	tf-init-obs-dev \
	tf-validate-obs-dev \
	tf-plan-obs-dev \
	tf-apply-obs-dev \
	tf-destroy-plan-obs-dev \
	tf-destroy-obs-dev \
	tf-destroy-plan-dev \
	tf-destroy-dev \
	tf-destroy-plan-all \
	tf-destroy-all \
	docker-up \
	docker-down \
	docker-logs \
	docker-ps \
	obs-up \
	obs-down \
	obs-empty-s3-dev \
	obs-logs \
	obs-ps \
	obs-smoke \
	docker-smoke \
	docker-smoke-db \
	docker-smoke-openai \
	cloud-smoke \
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

.DEFAULT_GOAL := help

# Runtime paths and process metadata
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
OBS_COMPOSE_FILE := docker-compose.observability.yml
OBS_ENV_FILE := .env.observability
OBS_PROJECT_NAME ?= research_to_blog_system_obs
OBS_DOCKER_COMPOSE := COMPOSE_PROJECT_NAME=$(OBS_PROJECT_NAME) docker compose --env-file $(OBS_ENV_FILE) -f $(OBS_COMPOSE_FILE)
TF_DEV_DIR := infra/terraform/envs/dev
TF_OBS_DEV_DIR := infra/terraform/envs/observability-dev

# Cloud release defaults
AWS_PROFILE ?= personal-aws-dev
AWS_REGION ?= us-west-2
# Leave unset to resolve dynamically via AWS STS at runtime.
AWS_ACCOUNT_ID ?=
PROJECT_NAME ?= vc-blog-agent
CLOUD_ENV ?= dev
IMAGE_PLATFORM ?= linux/amd64
RELEASE_SERVICES ?= api,worker,ui
SMOKE_LLM_MODE ?= mock
# Optional: when true, destroy targets purge images in ECR repositories first.
PURGE_ECR_ON_DESTROY ?= false
# Optional: when true, observability destroy targets purge Langfuse S3 buckets first.
PURGE_OBS_S3_ON_DESTROY ?= false
# Derived dev ECR repository names for app services.
DEV_ECR_REPOS := $(PROJECT_NAME)-$(CLOUD_ENV)-api $(PROJECT_NAME)-$(CLOUD_ENV)-worker $(PROJECT_NAME)-$(CLOUD_ENV)-ui
# Align local release defaults with CI behavior (immutable commit tag).
IMAGE_TAG ?= $(shell git rev-parse --short=12 HEAD 2>/dev/null || echo latest)
RELEASE_CMD := uv run python scripts/release.py
RELEASE_COMMON_ARGS := \
	--aws-profile "$(AWS_PROFILE)" \
	--aws-region "$(AWS_REGION)" \
	--aws-account-id "$(AWS_ACCOUNT_ID)" \
	--project-name "$(PROJECT_NAME)" \
	--cloud-env "$(CLOUD_ENV)" \
	--tf-workdir "$(TF_DEV_DIR)" \
	--tf-var-file "terraform.tfvars" \
	--image-tag "$(IMAGE_TAG)" \
	--image-platform "$(IMAGE_PLATFORM)" \
	--services "$(RELEASE_SERVICES)"

help: ## Show available make targets.
	@awk 'BEGIN {FS = ":.*##"; print "Usage: make <target>"} \
		/^##@/ {print ""; print substr($$0, 5)} \
		/^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-24s %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

##@ Local Development
sync: ## Install/update dependencies with uv.
	uv sync --all-groups

fmt: ## Format Python code with Black.
	uv run black .

lint: ## Run Ruff lint checks.
	uv run ruff check .

##@ Testing
test: test-unit test-integration test-e2e ## Run unit, integration, and e2e tests.

test-unit: ## Run unit tests.
	uv run pytest tests/unit

test-integration: ## Run integration tests.
	uv run pytest tests/integration

test-e2e: ## Run UI lifecycle e2e tests.
	uv run pytest tests/e2e

test-gate: ## Run strict pre-cloud API readiness test suite.
	uv run pytest \
		tests/integration/test_phase2_api_worker.py \
		tests/integration/test_api_readiness_gate.py \
		tests/performance/test_generate_enqueue_latency.py

test-perf: ## Run enqueue latency performance test.
	uv run pytest tests/performance/test_generate_enqueue_latency.py

##@ Cloud Release
ecr-login-dev: ## Authenticate Docker to the dev ECR registry.
	@account_id="$${AWS_ACCOUNT_ID:-$$(AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
		aws sts get-caller-identity --query Account --output text)}"; \
	registry="$$account_id.dkr.ecr.$(AWS_REGION).amazonaws.com"; \
	echo "Using ECR registry: $$registry"; \
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
		aws ecr get-login-password | docker login \
		--username AWS --password-stdin "$$registry"

ecr-empty-dev: ## Delete all images from dev ECR app repositories (api/worker/ui).
	@set -eu; \
	for repo in $(DEV_ECR_REPOS); do \
		echo "Checking ECR repo: $$repo"; \
		if ! AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
			aws ecr describe-repositories --repository-names "$$repo" >/dev/null 2>&1; then \
			echo "Skipping missing repository: $$repo"; \
			continue; \
		fi; \
		tmp=$$(mktemp); \
		AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
			aws ecr list-images --repository-name "$$repo" \
			--query 'imageIds' --output json > "$$tmp"; \
		count=$$(AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
			aws ecr list-images --repository-name "$$repo" \
			--query 'length(imageIds)' --output text); \
		if [ "$$count" = "0" ]; then \
			echo "Repository already empty: $$repo"; \
			rm -f "$$tmp"; \
			continue; \
		fi; \
		echo "Deleting $$count image refs from $$repo"; \
		AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
			aws ecr batch-delete-image --repository-name "$$repo" \
			--image-ids "file://$$tmp" >/dev/null; \
		rm -f "$$tmp"; \
	done

image-build-dev: ## Build API/worker/UI images for dev.
	$(RELEASE_CMD) build $(RELEASE_COMMON_ARGS)

image-push-dev: ## Build and push images to ECR.
	$(RELEASE_CMD) build-push $(RELEASE_COMMON_ARGS)

check-image-tag-sync: ## Guard IMAGE_TAG usage for deploy path consistency.
	@tfvars_path="$(TF_DEV_DIR)/terraform.tfvars"; \
	if [ ! -f "$$tfvars_path" ]; then \
		echo "ERROR: $$tfvars_path not found."; \
		exit 1; \
	fi; \
	tfvars_tag=$$(sed -nE 's/^[[:space:]]*image_tag[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$$tfvars_path" | head -n 1); \
	if [ -z "$$tfvars_tag" ]; then \
		echo "ERROR: image_tag is not set in $$tfvars_path."; \
		exit 1; \
	fi; \
	if [ "$$tfvars_tag" = "latest" ]; then \
		echo "note: $$tfvars_path uses image_tag=latest; deploy commands still use IMAGE_TAG=$(IMAGE_TAG) via -var override."; \
		exit 0; \
	fi; \
	if [ "$(IMAGE_TAG)" != "$$tfvars_tag" ]; then \
		echo "ERROR: IMAGE_TAG=$(IMAGE_TAG) does not match $$tfvars_path image_tag=$$tfvars_tag."; \
		echo "Set IMAGE_TAG=$$tfvars_tag or update $$tfvars_path if this is intentional."; \
		exit 1; \
	fi

deploy-plan-dev: check-image-tag-sync ## Run Terraform plan for current IMAGE_TAG.
	$(RELEASE_CMD) plan $(RELEASE_COMMON_ARGS)

deploy-dev: check-image-tag-sync ## Build/push/apply/wait/smoke release flow.
	$(RELEASE_CMD) deploy $(RELEASE_COMMON_ARGS) \
		--smoke-llm-mode "$(SMOKE_LLM_MODE)"

rotate-api-auth-key-dev: ## Rotate deployed API auth key in cloud.
	@bash scripts/rotate_api_auth_key_dev.sh

bootstrap-dev: ## Sync AWS/GitHub/tfvars from ops/dev.bootstrap.env.
	uv run python scripts/bootstrap_env.py --config-file ops/dev.bootstrap.env

bootstrap-dev-dry-run: ## Print bootstrap actions without applying changes.
	uv run python scripts/bootstrap_env.py --dry-run \
		--config-file ops/dev.bootstrap.env

bootstrap-dev-plan: ## Bootstrap then run Terraform plan for obs+app stacks.
	uv run python scripts/bootstrap_env.py --config-file ops/dev.bootstrap.env \
		--terraform-plan

bootstrap-dev-apply: ## Bootstrap then run Terraform apply for obs+app stacks.
	uv run python scripts/bootstrap_env.py --config-file ops/dev.bootstrap.env \
		--terraform-apply

##@ Terraform
tf-fmt: ## Format Terraform files.
	terraform fmt -recursive infra/terraform

tf-init-dev: ## Initialize Terraform backend for dev.
	terraform -chdir=$(TF_DEV_DIR) init -reconfigure -backend-config=backend.hcl

tf-validate-dev: ## Validate Terraform config for dev.
	terraform -chdir=$(TF_DEV_DIR) validate

tf-plan-dev: ## Plan Terraform changes for dev (uses IMAGE_TAG override).
	terraform -chdir=$(TF_DEV_DIR) plan -var-file=terraform.tfvars -var=image_tag=$(IMAGE_TAG)

tf-apply-dev: ## Apply Terraform changes for dev (uses IMAGE_TAG override).
	terraform -chdir=$(TF_DEV_DIR) apply -var-file=terraform.tfvars -var=image_tag=$(IMAGE_TAG)

tf-init-obs-dev: ## Initialize Terraform backend for observability dev.
	terraform -chdir=$(TF_OBS_DEV_DIR) init -reconfigure \
		-backend-config=backend.hcl

tf-validate-obs-dev: ## Validate Terraform config for observability dev.
	terraform -chdir=$(TF_OBS_DEV_DIR) validate

tf-plan-obs-dev: ## Plan Terraform changes for observability dev.
	terraform -chdir=$(TF_OBS_DEV_DIR) plan -var-file=terraform.tfvars

tf-apply-obs-dev: ## Apply Terraform changes for observability dev.
	terraform -chdir=$(TF_OBS_DEV_DIR) apply -var-file=terraform.tfvars

tf-destroy-plan-obs-dev: ## Show what observability-dev destroy would remove (no changes applied).
	terraform -chdir=$(TF_OBS_DEV_DIR) plan -destroy -var-file=terraform.tfvars

tf-destroy-obs-dev: ## Destroy observability-dev stack (optional: PURGE_OBS_S3_ON_DESTROY=true).
	@if [ "$(PURGE_OBS_S3_ON_DESTROY)" = "true" ]; then \
		echo "Purging Langfuse S3 buckets before observability destroy (PURGE_OBS_S3_ON_DESTROY=true)"; \
		$(MAKE) obs-empty-s3-dev; \
	else \
		echo "Skipping Langfuse S3 purge. Set PURGE_OBS_S3_ON_DESTROY=true to empty buckets first."; \
	fi
	terraform -chdir=$(TF_OBS_DEV_DIR) destroy -var-file=terraform.tfvars

tf-destroy-plan-dev: ## Show what dev destroy would remove (no changes applied).
	terraform -chdir=$(TF_DEV_DIR) plan -destroy -var-file=terraform.tfvars

tf-destroy-dev: ## Destroy dev stack (optional: PURGE_ECR_ON_DESTROY=true).
	@if [ "$(PURGE_ECR_ON_DESTROY)" = "true" ]; then \
		echo "Purging ECR images before destroy (PURGE_ECR_ON_DESTROY=true)"; \
		$(MAKE) ecr-empty-dev; \
	else \
		echo "Skipping ECR purge. Set PURGE_ECR_ON_DESTROY=true to empty repos first."; \
	fi
	terraform -chdir=$(TF_DEV_DIR) destroy -var-file=terraform.tfvars

tf-destroy-plan-all: ## Show what destroying observability-dev and dev would remove (no changes applied).
	@$(MAKE) tf-destroy-plan-obs-dev
	@$(MAKE) tf-destroy-plan-dev

tf-destroy-all: ## Destroy obs+dev stacks (requires CONFIRM_DESTROY_ALL=true; optional PURGE_OBS_S3_ON_DESTROY/PURGE_ECR_ON_DESTROY=true).
	@if [ "$(CONFIRM_DESTROY_ALL)" != "true" ]; then \
		echo "Refusing destroy-all. Re-run with CONFIRM_DESTROY_ALL=true"; \
		exit 1; \
	fi
	@$(MAKE) tf-destroy-obs-dev
	@$(MAKE) tf-destroy-dev

##@ Docker
docker-up: ## Start local Docker stack.
	$(DOCKER_COMPOSE) up --build -d

docker-down: ## Stop local Docker stack.
	$(DOCKER_COMPOSE) down --remove-orphans

docker-logs: ## Tail local Docker stack logs.
	$(DOCKER_COMPOSE) logs -f --tail=200

docker-ps: ## List local Docker stack service status.
	$(DOCKER_COMPOSE) ps

obs-up: ## Start separate Langfuse observability stack.
	@if [ ! -f $(OBS_ENV_FILE) ]; then \
		echo "Missing $(OBS_ENV_FILE)."; \
		echo "Create it from .env.observability.example first."; \
		exit 1; \
	fi
	$(OBS_DOCKER_COMPOSE) up -d

obs-down: ## Stop separate Langfuse observability stack.
	$(OBS_DOCKER_COMPOSE) down --remove-orphans

obs-empty-s3-dev: ## Delete objects in Langfuse event/media S3 buckets from observability-dev outputs.
	@set -eu; \
	event_bucket=$$(terraform -chdir=$(TF_OBS_DEV_DIR) output -raw langfuse_event_bucket_name 2>/dev/null || true); \
	media_bucket=$$(terraform -chdir=$(TF_OBS_DEV_DIR) output -raw langfuse_media_bucket_name 2>/dev/null || true); \
	if [ -z "$$event_bucket" ] && [ -z "$$media_bucket" ]; then \
		echo "No Langfuse S3 bucket outputs found in $(TF_OBS_DEV_DIR)."; \
		echo "Run tf-init-obs-dev/tf-apply-obs-dev first or skip this step."; \
		exit 0; \
	fi; \
	for bucket in $$event_bucket $$media_bucket; do \
		[ -n "$$bucket" ] || continue; \
		echo "Checking bucket: $$bucket"; \
		if ! AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
			aws s3api head-bucket --bucket "$$bucket" >/dev/null 2>&1; then \
			echo "Skipping missing/inaccessible bucket: $$bucket"; \
			continue; \
		fi; \
		echo "Deleting objects from s3://$$bucket"; \
		AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) \
			aws s3 rm "s3://$$bucket" --recursive >/dev/null || true; \
	done

obs-logs: ## Tail Langfuse observability stack logs.
	$(OBS_DOCKER_COMPOSE) logs -f --tail=200

obs-ps: ## List Langfuse observability stack service status.
	$(OBS_DOCKER_COMPOSE) ps

obs-smoke: ## Quick smoke check for local Langfuse web endpoint.
	@curl -fsS http://127.0.0.1:3000 >/dev/null && \
		echo "Langfuse web is reachable at http://127.0.0.1:3000"

docker-smoke: ## Run API lifecycle smoke test against Docker stack.
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

docker-smoke-db: ## Run smoke + direct Postgres persistence check.
	@bash scripts/docker_smoke_db_check.sh $(DOCKER_COMPOSE_FILE)

docker-smoke-openai: ## Run OpenAI-backed API smoke test in Docker.
	@bash scripts/docker_smoke_openai_check.sh $(DOCKER_COMPOSE_FILE)

cloud-smoke: ## Run health/readiness + lifecycle smoke test against deployed cloud API.
	@if [ ! -f $(RUN_DIR)/cloud_api_auth_key.txt ]; then \
		echo "Missing $(RUN_DIR)/cloud_api_auth_key.txt."; \
		echo "Add the deployed API key there before running cloud-smoke."; \
		exit 1; \
	fi
	@set -eu; \
	api_key=$$(cat $(RUN_DIR)/cloud_api_auth_key.txt); \
	base="$${CLOUD_API_BASE_URL:-https://api.blog-agent.dev.vc-projects-ds.com}"; \
	echo "Checking $$base/health"; \
	health=$$(curl -fsS "$$base/health" -H "x-api-key: $$api_key"); \
	echo "$$health" | jq .; \
	echo "Checking $$base/readiness"; \
	ready=$$(curl -fsS "$$base/readiness" -H "x-api-key: $$api_key"); \
	echo "$$ready" | jq .; \
	topic="cloud_smoke_$$(date +%s)"; \
	resp=$$(curl -fsS -X POST "$$base/generate" \
		-H "content-type: application/json" \
		-H "x-api-key: $$api_key" \
		-d "{\"topic\":\"$$topic\",\"llm_mode\":\"mock\"}"); \
	echo "$$resp" | jq .; \
	job_id=$$(printf '%s' "$$resp" | python -c 'import json,sys; print(json.loads(sys.stdin.read(), strict=False)["job_id"])'); \
	final_status=""; \
	for i in $$(seq 1 60); do \
		out=$$(curl -fsS "$$base/status/$$job_id" -H "x-api-key: $$api_key"); \
		final_status=$$(printf '%s' "$$out" | python -c 'import json,sys; print(json.loads(sys.stdin.read(), strict=False).get("status",""))'); \
		echo "$$final_status"; \
		if [ "$$final_status" = "COMPLETED" ] || [ "$$final_status" = "FAILED" ] || [ "$$final_status" = "ESCALATED" ]; then \
			printf '%s' "$$out" | python -c 'import json,sys; data=json.loads(sys.stdin.read(), strict=False); import json as _j; print(_j.dumps({k:data.get(k) for k in ("job_id","status","llm_mode","error_message","updated_at")}, indent=2))'; \
			break; \
		fi; \
		sleep 2; \
	done; \
	if [ "$$final_status" != "COMPLETED" ] && [ "$$final_status" != "FAILED" ] && [ "$$final_status" != "ESCALATED" ]; then \
		echo "cloud-smoke timed out waiting for terminal status"; \
		exit 1; \
	fi

##@ Runtime
run-sync: ## Run synchronous graph harness.
	@mkdir -p $(RUN_DIR)
	@env UV_CACHE_DIR=$(UV_CACHE_DIR) \
		uv run python -m apps.run_phase1_sync "AI agents in production"

run-api: ## Run FastAPI server in foreground.
	@mkdir -p $(RUN_DIR)
	@env UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(API_CMD_PATTERN)

run-worker: ## Run Celery worker in foreground.
	@mkdir -p $(RUN_DIR)
	@env UV_CACHE_DIR=$(UV_CACHE_DIR) \
		uv run celery -A apps.worker.app.celery_app:celery_app worker -l info

run-ui: ## Run Streamlit UI in foreground.
	@mkdir -p $(RUN_DIR)
	@mkdir -p $(UI_HOME)
	@env HOME=$(UI_HOME) UV_CACHE_DIR=$(UV_CACHE_DIR) \
		uv run $(UI_CMD_PATTERN)

run-api-bg: ## Start FastAPI server in background.
	@mkdir -p $(RUN_DIR)
	@if [ -f $(API_PID_FILE) ] && kill -0 $$(cat $(API_PID_FILE)) 2>/dev/null; then \
		echo "API already running with PID $$(cat $(API_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec env UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(API_CMD_PATTERN)' \
		> $(RUN_DIR)/api.log 2>&1 & echo $$! > $(API_PID_FILE)
	@echo "API started with PID $$(cat $(API_PID_FILE))"

run-worker-bg: ## Start Celery worker in background.
	@mkdir -p $(RUN_DIR)
	@if [ -f $(WORKER_PID_FILE) ] && kill -0 $$(cat $(WORKER_PID_FILE)) 2>/dev/null; then \
		echo "Worker already running with PID $$(cat $(WORKER_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec env UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(WORKER_CMD_PATTERN)' \
		> $(RUN_DIR)/worker.log 2>&1 & echo $$! > $(WORKER_PID_FILE)
	@echo "Worker started with PID $$(cat $(WORKER_PID_FILE))"

run-ui-bg: ## Start Streamlit UI in background.
	@mkdir -p $(RUN_DIR)
	@mkdir -p $(UI_HOME)
	@if [ -f $(UI_PID_FILE) ] && kill -0 $$(cat $(UI_PID_FILE)) 2>/dev/null; then \
		echo "UI already running with PID $$(cat $(UI_PID_FILE))"; \
		exit 1; \
	fi
	@nohup sh -c 'exec env HOME=$(UI_HOME) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run $(UI_CMD_PATTERN)' \
		> $(RUN_DIR)/ui.log 2>&1 & echo $$! > $(UI_PID_FILE)
	@echo "UI started with PID $$(cat $(UI_PID_FILE))"

run-services-bg: run-api-bg run-worker-bg run-ui-bg ## Start API, worker, and UI in background.

debug-openai: ## Run simple OpenAI connectivity and key check.
	uv run python scripts/debug_openai.py

##@ Runtime Cleanup
stop-api: ## Stop API background process(es).
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

stop-worker: ## Stop worker background process(es).
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

stop-ui: ## Stop UI background process(es).
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

stop-services: stop-api stop-worker stop-ui ## Stop API, worker, and UI background processes.
