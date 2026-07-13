#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TENANT_SLUG="sdq-labs-growth-sandbox"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v curl >/dev/null || fail "curl is required"
for attempt in $(seq 1 30); do
  if curl -fsS "${API_BASE_URL}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${API_BASE_URL}/health" >/dev/null || fail "SDQ API is unavailable at ${API_BASE_URL}"
curl -fsS -X POST "${API_BASE_URL}/sandbox/sdq-labs-growth/bootstrap-tenant" >/dev/null \
  || fail "Could not bootstrap sandbox tenant"
curl -fsS "${API_BASE_URL}/tenants" | grep -q "\"slug\":\"${TENANT_SLUG}\"" \
  || curl -fsS "${API_BASE_URL}/tenants" | grep -q "\"slug\": \"${TENANT_SLUG}\"" \
  || fail "Sandbox tenant was not found after bootstrap"

echo "sandbox tenant ready: ${TENANT_SLUG}"
