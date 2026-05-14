#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MODEL_NAME="${MODEL_NAME:-gemma-4-e4b-it}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-5}"
MAX_TIME="${MAX_TIME:-45}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
PUBLIC_PORT="${PUBLIC_PORT:-8000}"
TEST_PUBLIC="${TEST_PUBLIC:-0}"
API_KEY="${API_KEY:-}"

curl_common=(
  -fsS
  --connect-timeout "${CONNECT_TIMEOUT}"
  --max-time "${MAX_TIME}"
  -H "Content-Type: application/json"
)

if [ -n "${API_KEY}" ]; then
  curl_common+=( -H "Authorization: Bearer ${API_KEY}" )
fi

resolve_public_base_url() {
  if [ -n "${PUBLIC_BASE_URL}" ]; then
    printf '%s\n' "${PUBLIC_BASE_URL}"
    return 0
  fi

  public_ip="$({
    curl -fsS \
      --connect-timeout 2 \
      --max-time 3 \
      -H "Metadata-Flavor: Google" \
      http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip
  } 2>/dev/null || true)"

  if [ -n "${public_ip}" ]; then
    printf 'http://%s:%s\n' "${public_ip}" "${PUBLIC_PORT}"
  fi
}

run_smoke_test() {
  local label="$1"
  local base_url="$2"

  echo "==> ${label}: ${base_url}"

  curl "${curl_common[@]}" "${base_url}/v1/models"

  echo

  curl "${curl_common[@]}" "${base_url}/v1/chat/completions" \
    -d "{
      \"model\": \"${MODEL_NAME}\",
      \"messages\": [
        {\"role\": \"system\", \"content\": \"You are a concise assistant.\"},
        {\"role\": \"user\", \"content\": \"Hãy tự giới thiệu bản thân bạn đi, bằng 20 từ\"}
      ],
      \"max_tokens\": 64,
      \"temperature\": 0.2
    }"

  echo
  echo "Smoke test completed for ${label}"
}

run_smoke_test "configured endpoint" "${BASE_URL}"

if [ "${TEST_PUBLIC}" = "1" ] || [ -n "${PUBLIC_BASE_URL}" ]; then
  resolved_public_base_url="$(resolve_public_base_url)"

  if [ -z "${resolved_public_base_url}" ]; then
    echo "Unable to resolve a public endpoint. Set PUBLIC_BASE_URL or assign an external IP first." >&2
    exit 1
  fi

  if [ "${resolved_public_base_url}" != "${BASE_URL}" ]; then
    echo
    run_smoke_test "public endpoint" "${resolved_public_base_url}"
  fi
fi