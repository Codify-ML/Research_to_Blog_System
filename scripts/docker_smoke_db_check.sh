#!/usr/bin/env bash
set -euo pipefail

compose_file="${1:-docker-compose.local.yml}"
compose_cmd=(docker compose -f "$compose_file")

post_body='{"topic":"Docker Postgres persistence check","llm_mode":"mock"}'

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

echo "Tracking job_id=$job_id"

terminal_status=""
for _ in $(seq 1 60); do
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
    break
  fi

  sleep 1
done

if [[ -z "$terminal_status" ]]; then
  echo "ERROR: job did not reach a terminal status within timeout"
  exit 1
fi

db_payload="$(
  "${compose_cmd[@]}" exec -T postgres /bin/sh -lc \
    "psql -U postgres -d research_blog -t -A \
    -c \"SELECT payload::text FROM jobs WHERE job_id = '$job_id'\""
)"

if [[ -z "$db_payload" ]]; then
  echo "ERROR: no row found in Postgres jobs table for $job_id"
  exit 1
fi

db_status="$(
  python -c \
    'import json,sys; print(json.loads(sys.argv[1])["status"])' \
    "$db_payload"
)"

db_transition_count="$(
  python -c \
    'import json,sys; print(len(json.loads(sys.argv[1])["status_transitions"]))' \
    "$db_payload"
)"

echo "Postgres status=$db_status transitions=$db_transition_count"

if [[ "$db_status" != "$terminal_status" ]]; then
  echo "ERROR: Postgres status mismatch ($db_status != $terminal_status)"
  exit 1
fi

if [[ "$db_transition_count" -lt 2 ]]; then
  echo "ERROR: expected at least 2 transitions in Postgres payload"
  exit 1
fi

echo "Postgres persistence verification passed for $job_id"
