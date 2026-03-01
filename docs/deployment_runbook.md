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

