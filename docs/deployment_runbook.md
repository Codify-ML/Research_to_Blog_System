# Deployment Runbook

This runbook documents the end-to-end deployment flow for local and cloud
environments.

## Scope
- App stack: UI, API, worker, Redis, Postgres.
- Observability stack: Langfuse (optional, separate stack).

## Prerequisites
- Docker Desktop running.
- `uv` installed.
- AWS CLI configured.
- Terraform installed.
- GitHub environment variables/secrets configured for CI deploys.

For local terminal-driven cloud deploys in this repo, use:

```bash
export AWS_PROFILE=personal-aws-dev
export AWS_REGION=us-west-2
```

## 1) Local Docker Deployment (App Stack)

1. Create env file if missing:
```bash
cp .env.example .env
```
2. Start stack:
```bash
make docker-up
```
3. Validate:
```bash
make docker-ps
make docker-smoke
make docker-smoke-db
```
4. Stop stack:
```bash
make docker-down
```

## 2) Local Docker Deployment (Observability Stack)

1. Create observability env file:
```bash
cp .env.observability.example .env.observability
```
2. Start stack:
```bash
make obs-up
```
3. Validate:
```bash
make obs-ps
make obs-smoke
```
4. Stop stack:
```bash
make obs-down
```

## 3) Cloud Deployment (Recommended Bootstrap Path)

This path keeps AWS Secrets, GitHub environment values, and Terraform tfvars
in sync.

1. Copy bootstrap template:
```bash
cp ops/dev.bootstrap.env.example ops/dev.bootstrap.env
```
2. Fill required values in `ops/dev.bootstrap.env`.
3. Dry run:
```bash
make bootstrap-dev-dry-run
```
4. Apply sync:
```bash
make bootstrap-dev
```
5. Plan both stacks:
```bash
make bootstrap-dev-plan
```
6. Apply both stacks:
```bash
make bootstrap-dev-apply
```
7. Validate app stack:
```bash
make cloud-smoke
```

## 4) Cloud Deployment (Manual Path)

Use this when you explicitly want to separate infrastructure apply from release
image rollout.

### 4.1 Infrastructure
1. Prepare tfvars:
```bash
cp infra/terraform/envs/dev/terraform.tfvars.example \
  infra/terraform/envs/dev/terraform.tfvars
```
2. Init/validate/plan:
```bash
make tf-init-dev
make tf-validate-dev
make tf-plan-dev
```
3. Apply:
```bash
make tf-apply-dev
```

### 4.2 App Release (images + ECS update)

By default, `IMAGE_TAG` resolves to current git SHA (12 chars).

```bash
make image-build-dev
make image-push-dev
make deploy-plan-dev
make deploy-dev
make cloud-smoke
```

If you need a specific tag:

```bash
IMAGE_TAG=<tag> make deploy-dev
```

## 5) CI/CD Deployment Flow

Workflow: `.github/workflows/build-and-push-images.yml`

- PR to `main`: build + plan.
- Non-`main` push: build + plan (default).
- `main` push: deploy (build/push/apply/stabilize/smoke).
- Optional feature-branch deploy override:
  - `ENABLE_FEATURE_DEPLOY=true`
  - `FEATURE_DEPLOY_REF=refs/heads/<branch>`

## 6) Post-Deploy Checks

1. API health/readiness:
```bash
API_KEY=$(cat .run/cloud_api_auth_key.txt)
curl -sS https://api.blog-agent.dev.vc-projects-ds.com/health -H "x-api-key: ${API_KEY}" | jq .
curl -sS https://api.blog-agent.dev.vc-projects-ds.com/readiness -H "x-api-key: ${API_KEY}" | jq .
```
2. UI:
- Open `https://ui.blog-agent.dev.vc-projects-ds.com`.
3. Langfuse (if enabled):
- Open `https://langfuse.blog-agent.dev.vc-projects-ds.com`.

## 7) Rollback Strategy

1. Redeploy a known-good image tag:
```bash
IMAGE_TAG=<known_good_sha> make deploy-dev
```
2. Re-run smoke:
```bash
make cloud-smoke
```

## 8) Teardown and Cost Control

Use these targets to safely inspect or remove cloud resources when not needed.

### 8.1 Preview what would be destroyed (no deletion)
```bash
make tf-destroy-plan-obs-dev
make tf-destroy-plan-dev
make tf-destroy-plan-all
```

### 8.2 Destroy only observability stack
```bash
make tf-destroy-obs-dev
```

If destroy fails due to non-empty Langfuse S3 buckets, purge buckets first:

```bash
make tf-destroy-obs-dev PURGE_OBS_S3_ON_DESTROY=true
```

### 8.3 Destroy only app stack (dev)
By default, ECR images are preserved.

```bash
make tf-destroy-dev
```

To purge app images in ECR before destroying:

```bash
make tf-destroy-dev PURGE_ECR_ON_DESTROY=true
```

### 8.4 Destroy both stacks
Guarded to prevent accidental full teardown.

```bash
make tf-destroy-all CONFIRM_DESTROY_ALL=true
```

To also purge app ECR images:

```bash
make tf-destroy-all CONFIRM_DESTROY_ALL=true PURGE_ECR_ON_DESTROY=true
```

To purge both Langfuse S3 buckets and app ECR images:

```bash
make tf-destroy-all CONFIRM_DESTROY_ALL=true PURGE_OBS_S3_ON_DESTROY=true PURGE_ECR_ON_DESTROY=true
```

### 8.5 ECR-only cleanup
If you only want to remove app images from ECR:

```bash
make ecr-empty-dev
```

If you only want to remove Langfuse objects from S3 buckets:

```bash
make obs-empty-s3-dev
```

## 9) Phase 2 Cost Controls: Scheduled Scaling

Scheduled scaling is implemented but disabled by default.

### 9.1 App stack (`infra/terraform/envs/dev/terraform.tfvars`)

```hcl
enable_scheduled_scaling = true
scheduled_scale_up_recurrence = "cron(0 8 ? * MON-FRI *)"
scheduled_scale_down_recurrence = "cron(0 20 ? * MON-FRI *)"
scheduled_scaling_timezone = "America/Los_Angeles"
api_offhours_count = 0
worker_offhours_count = 0
ui_offhours_count = 0
ui_logout_offhours_count = 0
```

### 9.2 Observability stack (`infra/terraform/envs/observability-dev/terraform.tfvars`)

```hcl
enable_scheduled_scaling = true
scheduled_scale_up_recurrence = "cron(0 8 ? * MON-FRI *)"
scheduled_scale_down_recurrence = "cron(0 20 ? * MON-FRI *)"
scheduled_scaling_timezone = "America/Los_Angeles"
langfuse_web_offhours_count = 0
langfuse_worker_offhours_count = 0
langfuse_clickhouse_offhours_count = 0
```

Apply after setting values:

```bash
make tf-apply-dev
make tf-apply-obs-dev
```
