#!/usr/bin/env bash
set -euo pipefail

compose_file="${1:-docker-compose.local.yml}"
compose_cmd=(docker compose -f "$compose_file")

has_key="$(
  "${compose_cmd[@]}" exec -T api /bin/sh -lc \
    'python -c "import os; print(1 if os.getenv(\"OPENAI_API_KEY\") else 0)"'
)"

if [[ "$has_key" != "1" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set in the api container environment."
  echo "Set OPENAI_API_KEY in your local .env (or compose --env-file)."
  exit 1
fi

post_body='{"topic":"Docker OpenAI smoke run","llm_mode":"openai"}'

response="$(
  "${compose_cmd[@]}" exec -T api /bin/sh -lc \
    "curl -sS -X POST http://127.0.0.1:8000/generate \
    -H 'content-type: application/json' -d '$post_body'"
)"

echo "$response"

job_id="$(
  python -c \
    'import json,sys; print(json.loads(sys.argv[1])["job_id"])' \
    "$response"
)"

echo "Tracking job_id=$job_id (llm_mode=openai)"

terminal_status=""
terminal_payload=""
for _ in $(seq 1 90); do
  status_json="$(
    "${compose_cmd[@]}" exec -T api /bin/sh -lc \
      "curl -sS http://127.0.0.1:8000/status/$job_id"
  )"
  current_status="$(
    python -c \
      'import json,sys; print(json.loads(sys.argv[1])["status"])' \
      "$status_json"
  )"
  echo "$current_status"

  if [[ "$current_status" == "COMPLETED" \
    || "$current_status" == "FAILED" \
    || "$current_status" == "ESCALATED" ]]; then
    terminal_status="$current_status"
    terminal_payload="$status_json"
    echo "$status_json"
    break
  fi

  sleep 1
done

if [[ -z "$terminal_status" ]]; then
  echo "ERROR: OpenAI smoke job did not reach terminal status in time."
  exit 1
fi

if [[ "$terminal_status" == "FAILED" ]]; then
  error_msg="$(
    python -c \
      'import json,sys; print(json.loads(sys.argv[1]).get("error_message") or "")' \
      "$terminal_payload"
  )"
  echo "ERROR: OpenAI smoke reached FAILED. error_message=$error_msg"
  exit 1
fi

echo "OpenAI Docker smoke passed with terminal status=$terminal_status"
