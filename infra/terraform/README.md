# Terraform (Phase 5 Scaffold)

This directory contains the initial cloud deployment scaffold for the
Research-to-Blog system.

## Layout

- `envs/dev`: environment root module and backend config.
- `modules/network`: VPC, subnets, routing.
- `modules/security`: security groups and ECS IAM roles.
- `modules/data`: RDS Postgres and ElastiCache Redis.
- `modules/compute`: ECS/Fargate services and ALBs.
- `modules/secrets`: Secrets Manager secret for OpenAI key.
- `modules/ecr`: ECR repositories for API, worker, and UI images.

## Backend (dev)

The `dev` environment is configured for S3 remote state with:

- Bucket: `vc-tfstate-deploy-dev`
- Key: `projects/vc-blog-agent/terraform/state/dev.tfstate`
- Profile: `personal-aws-dev`
- Locking: `use_lockfile = true`

## Usage (dev)

From repository root:

```bash
make tf-init-dev
make tf-validate-dev
make tf-plan-dev
```

No `apply` is run automatically. Review the plan first.

## Cloud Portability Notes

- ECS services run in private subnets with `assign_public_ip = false`.
- Public ALBs terminate ingress and route to ECS targets in private subnets.
- NAT gateway is enabled by default for private egress (ECR pulls,
  OpenAI API calls, CloudWatch logs, etc.).
- HTTPS is enabled by default with ACM DNS validation and Route53 alias
  records for API/UI hostnames.
- UI ALB uses Cognito hosted login (`authenticate-cognito`) for access
  control at the edge.
- API shared-key auth can be enabled with `api_auth_enabled=true`.
  The API key is stored in Secrets Manager and injected into API/UI tasks.
- RDS now uses AWS-managed master credentials
  (`manage_master_user_password = true`), with the generated secret ARN
  exposed as `db_master_secret_arn`.
- A regional WAF is associated with both ALBs (managed rules + rate limit).
- If `api_image`, `worker_image`, and `ui_image` are empty, Terraform
  composes image URIs from created ECR repositories and `image_tag`.

## RDS Secret Migration Note

For existing stacks that previously used plaintext `db_password`, run apply
twice during migration:

1. First apply enables `manage_master_user_password` on RDS.
2. Second apply wires ECS DB secret injection and IAM access using the now
   available RDS secret ARN.

## CI Image Pipeline

The workflow `.github/workflows/build-and-push-images.yml` builds and pushes
API/worker/UI images to ECR (`<project>-<env>-{api,worker,ui}`).

Required GitHub Environment variables:
- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `PROJECT_NAME`
- `CLOUD_ENV`
- `TF_WORKDIR`
- `IMAGE_PLATFORM`

Optional GitHub Environment variables:
- `ENABLE_FEATURE_DEPLOY`
- `FEATURE_DEPLOY_REF`

Required GitHub Environment secrets:
- `AWS_ROLE_TO_ASSUME` (OIDC role)
- `API_AUTH_KEY`
- `OPENAI_API_KEY`

Optional GitHub Environment secret:
- `AWS_ROLE_EXTERNAL_ID`

## Authentication Operations

User onboarding, disable/enable, and access control steps are documented in:

- `infra/terraform/authentication_runbook.md`
