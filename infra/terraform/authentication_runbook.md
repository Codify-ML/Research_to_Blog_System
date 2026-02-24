# Authentication Runbook (Dev)

This runbook describes how UI authentication works for the dev environment and
how to manage access for demo users.

## Architecture

- UI traffic goes through the UI ALB.
- The UI ALB HTTPS listener enforces `authenticate-cognito`.
- Path `/auth/logout` is routed to a dedicated logout service and bypasses
  `authenticate-cognito`.
- Unauthenticated users are redirected to Cognito Hosted UI login.
- After login, ALB forwards requests to the Streamlit UI service.
- API requests are protected with app-layer shared-key auth
  (`X-API-Key`) when `API_AUTH_ENABLED=true`.

## Who Can Authenticate

- Only users in the Cognito User Pool created by Terraform.
- User signup is disabled (`allow_admin_create_user_only = true`).
- Users are created by admins/operators only.

## Admin Model

- IAM controls who can manage Cognito users.
- Recommended:
- Create an IAM group/role for app admins.
- Grant only required Cognito actions for this specific user pool.
- Do not share root or broad admin credentials.

## User Lifecycle Operations

Use AWS CLI with your local profile:

```bash
export AWS_PROFILE=personal-aws-dev
export AWS_REGION=us-west-2
```

Discover pool ID (after `terraform apply`):

```bash
terraform -chdir=infra/terraform/envs/dev output -raw cognito_user_pool_id
```

### Create User

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <POOL_ID> \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL
```

### Force Password Reset (Optional)

```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id <POOL_ID> \
  --username user@example.com \
  --password '<StrongTempPassword123!>' \
  --no-permanent
```

Notes:
- Use `--no-permanent` to force the user to set a new password at next login.
- Use `--permanent` only when you do not want a forced password change.

### Disable User

```bash
aws cognito-idp admin-disable-user \
  --user-pool-id <POOL_ID> \
  --username user@example.com
```

### Re-enable User

```bash
aws cognito-idp admin-enable-user \
  --user-pool-id <POOL_ID> \
  --username user@example.com
```

### Delete User

```bash
aws cognito-idp admin-delete-user \
  --user-pool-id <POOL_ID> \
  --username user@example.com
```

## Demo Workflow

1. Apply Terraform.
2. Create one or more Cognito users (admin action).
3. Set API shared key in Secrets Manager (if API auth is enabled).
4. Open `https://ui.vc-blog-agent.dev.vc-projects-ds.com`.
5. User logs in via Cognito Hosted UI.
6. User reaches Streamlit UI only after successful auth.

## Sign Out

The UI provides account controls:

- `Sign Out`: calls `/auth/logout`, expires ALB auth cookies server-side,
  then redirects to Cognito `/logout` and back to UI.

## Security Notes

- Keep Cognito admin permissions restricted to a small operator group.
- Keep OpenAI key in AWS Secrets Manager; do not place it in plain env vars.
- Keep WAF enabled and tune rate limits as traffic patterns become clear.
