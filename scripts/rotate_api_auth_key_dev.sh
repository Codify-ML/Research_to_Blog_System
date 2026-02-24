#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${RUN_DIR:-$ROOT_DIR/.run}"
KEY_FILE="${KEY_FILE:-$RUN_DIR/cloud_api_auth_key.txt}"
IMAGE_TAG_FILE="${IMAGE_TAG_FILE:-$RUN_DIR/cloud_image_tag.txt}"
TF_DIR="${TF_DIR:-$ROOT_DIR/infra/terraform/envs/dev}"
TF_VAR_FILE="${TF_VAR_FILE:-terraform.tfvars}"

AWS_PROFILE="${AWS_PROFILE:-personal-aws-dev}"
AWS_REGION="${AWS_REGION:-us-west-2}"
PROJECT_NAME="${PROJECT_NAME:-vc-blog-agent}"
CLOUD_ENV="${CLOUD_ENV:-dev}"
ECS_CLUSTER="${ECS_CLUSTER:-${PROJECT_NAME}-${CLOUD_ENV}-cluster}"

SERVICES=(
  "${PROJECT_NAME}-${CLOUD_ENV}-api"
  "${PROJECT_NAME}-${CLOUD_ENV}-worker"
  "${PROJECT_NAME}-${CLOUD_ENV}-ui"
)

NEW_KEY="${NEW_KEY:-}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--api-key <value>]

Rotates API_AUTH_KEY in deployed cloud services by:
1) generating (or using provided) API key
2) updating .run/cloud_api_auth_key.txt
3) running terraform apply with TF_VAR_api_auth_key
4) forcing ECS redeploy for api/worker/ui
5) waiting for ECS services to become stable

Notes:
- This does NOT update GitHub secrets.
- OPENAI key is read from TF_VAR_openai_api_key or .env if needed.
EOF
}

mask_value() {
  local value="$1"
  local length="${#value}"
  if [ "$length" -le 8 ]; then
    printf "***"
    return
  fi
  printf "%s...%s" "${value:0:4}" "${value:length-4:4}"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --api-key)
        shift
        NEW_KEY="${1:-}"
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
    shift
  done
}

load_openai_key_from_env_file() {
  local env_file="$ROOT_DIR/.env"
  if [ -n "${TF_VAR_openai_api_key:-}" ]; then
    return
  fi
  if [ ! -f "$env_file" ]; then
    return
  fi

  local maybe_key
  maybe_key="$(grep '^OPENAI_API_KEY=' "$env_file" | tail -n 1 | cut -d= -f2-)"
  if [ -n "$maybe_key" ]; then
    export TF_VAR_openai_api_key="$maybe_key"
  fi
}

build_new_key() {
  if [ -n "$NEW_KEY" ]; then
    echo "$NEW_KEY"
    return
  fi
  openssl rand -hex 32
}

main() {
  parse_args "$@"

  require_cmd aws
  require_cmd terraform
  require_cmd openssl
  require_cmd curl

  if [ ! -f "$IMAGE_TAG_FILE" ]; then
    echo "Missing image tag file: $IMAGE_TAG_FILE" >&2
    echo "Set IMAGE_TAG_FILE or create .run/cloud_image_tag.txt first." >&2
    exit 1
  fi

  local image_tag
  image_tag="$(tr -d '[:space:]' < "$IMAGE_TAG_FILE")"
  if [ -z "$image_tag" ]; then
    echo "Image tag file is empty: $IMAGE_TAG_FILE" >&2
    exit 1
  fi

  local api_key
  api_key="$(build_new_key)"
  if [ -z "$api_key" ]; then
    echo "Failed to build a new API key." >&2
    exit 1
  fi

  local backup_file=""
  if [ -f "$KEY_FILE" ] && [ -s "$KEY_FILE" ]; then
    backup_file="${KEY_FILE%.txt}.pre_rotate_$(date +%Y%m%d%H%M%S).txt"
    cp "$KEY_FILE" "$backup_file"
    chmod 600 "$backup_file" || true
  fi

  mkdir -p "$RUN_DIR"
  printf "%s\n" "$api_key" > "$KEY_FILE"
  chmod 600 "$KEY_FILE" || true

  export TF_VAR_api_auth_key="$api_key"
  load_openai_key_from_env_file

  echo "Prepared new API key: $(mask_value "$api_key")"
  echo "Saved local key file: $KEY_FILE"
  if [ -n "$backup_file" ]; then
    echo "Backed up previous key file: $backup_file"
  fi
  echo "Using AWS profile/region: $AWS_PROFILE / $AWS_REGION"
  echo "Using image tag: $image_tag"

  AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
    terraform -chdir="$TF_DIR" apply \
    -var-file="$TF_VAR_FILE" \
    -var="image_tag=$image_tag" \
    -auto-approve

  for service in "${SERVICES[@]}"; do
    echo "Forcing new deployment: $service"
    AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
      aws ecs update-service \
      --cluster "$ECS_CLUSTER" \
      --service "$service" \
      --force-new-deployment >/dev/null
  done

  echo "Waiting for ECS services to stabilize..."
  AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
    aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "${SERVICES[@]}"

  echo "Verifying API /generate with rotated key..."
  local api_url
  api_url="$(
    AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
      terraform -chdir="$TF_DIR" output -raw api_url
  )"
  local verify_response_file
  verify_response_file="${RUN_DIR}/rotate_api_auth_key_generate_response.json"
  local generate_status
  generate_status="$(
    curl -sS -o "$verify_response_file" -w "%{http_code}" \
      -X POST "${api_url%/}/generate" \
      -H "content-type: application/json" \
      -H "x-api-key: $api_key" \
      -d '{"topic":"api auth rotation verification","llm_mode":"mock"}'
  )"
  echo "API /generate status: $generate_status"
  if [ "$generate_status" != "200" ]; then
    echo "Verification response body: $(cat "$verify_response_file")" >&2
    echo "Auth verification failed after key rotation." >&2
    exit 1
  fi

  echo
  echo "Rotation complete."
  echo "Next required step: update GitHub 'dev' environment secret API_AUTH_KEY"
  echo "with the same rotated value from: $KEY_FILE"
}

main "$@"
