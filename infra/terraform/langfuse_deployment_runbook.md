# Langfuse Cloud Deployment Runbook (Dev)

Recommended path: use the bootstrap orchestrator instead of manual secret
updates:

```bash
cp ops/dev.bootstrap.env.example ops/dev.bootstrap.env
make bootstrap-dev-dry-run
make bootstrap-dev
make bootstrap-dev-plan
make bootstrap-dev-apply
```

Bootstrap automatically manages Langfuse project keys for app tracing:
- reuses existing `langfuse_public_key` / `langfuse_secret_key` when present
- otherwise generates `lf_pk_*` / `lf_sk_*` and writes them to AWS Secrets
- also writes bootstrap-init project key secrets used by LANGFUSE_INIT_*

The manual steps below remain as fallback/debug procedures.

This runbook deploys Langfuse as a separate cloud stack from the app stack.

## 1) State Isolation

Langfuse uses its own Terraform backend key:

- Bucket: `vc-tfstate-deploy-dev`
- Key: `projects/vc-blog-agent/terraform/state/observability-dev.tfstate`

This prevents lock/state collisions with the app stack key:
`projects/vc-blog-agent/terraform/state/dev.tfstate`.

## 2) Required Inputs

Copy:

```bash
cp infra/terraform/envs/observability-dev/terraform.tfvars.example \
  infra/terraform/envs/observability-dev/terraform.tfvars
```

Then set values in
`infra/terraform/envs/observability-dev/terraform.tfvars` as needed.

Keep:

- `enable_langfuse_compute = false` for first apply (secrets only).
- `enable_langfuse_auth = true` to enforce ALB Cognito login.

## 3) Initialize and Apply Secrets-Only

```bash
make tf-init-obs-dev
make tf-plan-obs-dev
make tf-apply-obs-dev
```

This creates Secrets Manager entries under:
`vc-blog-agent/dev/langfuse/*`.

## 4) Push Secret Values

Set environment:

```bash
export AWS_PROFILE=personal-aws-dev
export AWS_REGION=us-west-2
export LF_PREFIX="vc-blog-agent/dev/langfuse"
```

Push values:

```bash
aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/database_url" \
  --secret-string "postgresql://<user>:<password>@<host>:5432/<db>"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/clickhouse_url" \
  --secret-string "http://<user>:<password>@<host>:8123"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/clickhouse_migration_url" \
  --secret-string "clickhouse://<user>:<password>@<host>:9000"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/redis_connection_string" \
  --secret-string "redis://<host>:6379"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/salt" \
  --secret-string "<random-32+-char-salt>"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/encryption_key" \
  --secret-string "<64-hex-chars>"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/nextauth_secret" \
  --secret-string "<random-32+-char-secret>"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/init_user_email" \
  --secret-string "<admin-email>"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/init_user_name" \
  --secret-string "<admin-name>"

aws secretsmanager put-secret-value \
  --secret-id "${LF_PREFIX}/init_user_password" \
  --secret-string "<strong-admin-password>"
```

## 5) Enable Compute and Deploy

Set in `infra/terraform/envs/observability-dev/terraform.tfvars`:

```hcl
enable_langfuse_compute = true
```

Also set (or keep defaults):

```hcl
langfuse_event_bucket_name = ""
langfuse_media_bucket_name = ""
langfuse_s3_retention_days = 7
langfuse_clickhouse_user   = "default"
langfuse_clickhouse_password = "langfuse"
langfuse_clickhouse_db     = "default"
```

Then deploy:

```bash
make tf-plan-obs-dev
make tf-apply-obs-dev
```

## 6) Verify

```bash
terraform -chdir=infra/terraform/envs/observability-dev output
```

Expected:

- `langfuse_url`
- `langfuse_alb_dns_name`
- `langfuse_cluster_name`

With `enable_langfuse_auth = true`, ALB enforces Cognito login using the
same user pool/client setup from the app stack.
