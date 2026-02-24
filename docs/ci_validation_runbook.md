# CI Validation Runbook

This runbook validates the branch behavior in
`.github/workflows/build-and-push-images.yml`.

## Scope
- `pull_request` to `main` runs `build` and then `plan`.
- `push` to non-`main` branches runs `build` and then `plan`.
- Optional feature-branch deploy override can run full `deploy` on a
  specific non-`main` ref.
- `push` to `main` runs full `deploy`:
  build/push/apply/wait/smoke.
- Manual `workflow_dispatch` runs the selected action.

## Prerequisites
- GitHub Environment `dev` exists.
- Environment variables are set:
  `AWS_REGION`, `AWS_ACCOUNT_ID`, `PROJECT_NAME`, `CLOUD_ENV`,
  `TF_WORKDIR`, `IMAGE_PLATFORM`.
- Optional environment variables for feature deploy override:
  `ENABLE_FEATURE_DEPLOY`, `FEATURE_DEPLOY_REF`.
- Environment secrets are set:
  `AWS_ROLE_TO_ASSUME`, `API_AUTH_KEY`, `OPENAI_API_KEY`.
- Optional secret:
  `AWS_ROLE_EXTERNAL_ID`.

## Test Matrix
| Scenario | Trigger | Expected Action |
|---|---|---|
| Feature branch push | `push` (`refs/heads/feature/*`) | `build` + `plan` |
| Feature deploy override | `push` where `ENABLE_FEATURE_DEPLOY=true` and `github.ref == FEATURE_DEPLOY_REF` | `deploy` |
| PR to main | `pull_request` target `main` | `build` + `plan` |
| Main merge/push | `push` (`refs/heads/main`) | `deploy` |
| Manual run | `workflow_dispatch` | selected input action |

## Validation Steps
1. Feature branch validation
   - Push a branch with a change in a tracked path
     (`apps/**`, `packages/**`, `docker/**`,
     `infra/terraform/**`, `scripts/release.py`, `Makefile`,
     `pyproject.toml`, `uv.lock`, workflow file).
   - Confirm `Cloud Release` starts.
   - Confirm `Build Docker images (PR/non-main validation)` runs.
   - In `Resolve release parameters`, confirm:
     `action=plan`, `services=api,worker,ui`, `run_smoke=false`.
   - Confirm logs run `terraform ... plan` and do not run apply.

2. PR validation
   - Open PR from feature branch into `main`.
   - Confirm run starts and includes Docker build validation.
   - Confirm run resolves to `action=plan`.
   - Confirm plan runs and apply does not run.

3. Main validation
   - Merge PR to `main`.
   - Confirm run resolves to:
     `action=deploy`, `run_smoke=true`.
   - Confirm logs include:
     docker build/push, terraform apply, ECS stable wait,
     smoke polling to terminal success.

4. Manual dispatch validation
   - Use `workflow_dispatch`.
   - Run `plan`, then `smoke` (`mock` and `openai`).
   - Confirm behavior matches selected action.

5. Feature deploy override validation (optional)
   - In GitHub Environment vars, set:
     `ENABLE_FEATURE_DEPLOY=true`
     and `FEATURE_DEPLOY_REF=refs/heads/<branch>`.
   - Push to that branch.
   - Confirm `Resolve release parameters` emits `action=deploy`.
   - Confirm logs include build/push/apply/wait/smoke.
   - Disable override after validation
     (`ENABLE_FEATURE_DEPLOY=false`).

## Acceptance Criteria
- No PR run performs apply.
- PR/non-main runs perform Docker build validation.
- Non-main pushes only perform deploy when explicit feature override is
  enabled and ref-matched.
- Main push performs deploy and smoke.
- Manual action selection behaves exactly as requested.

## Troubleshooting
- If workflow does not trigger:
  verify changed files match workflow `paths`.
- If environment variables are empty:
  verify job environment is `dev` and variables are defined there.
- If AWS auth fails:
  verify OIDC role trust and `AWS_ROLE_TO_ASSUME`.
- If plan fails with service mismatch:
  use all services (`api,worker,ui`) for `plan/apply/deploy`.
