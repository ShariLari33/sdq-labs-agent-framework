#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TENANT_SLUG="sdq-labs-growth-sandbox"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

"${ROOT_DIR}/scripts/bootstrap.sh" >/dev/null
code="$(curl -sS -o /tmp/sdq-growth-followup-import.json -w "%{http_code}" \
  -X POST "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/import" \
  -F "created_by=sandbox-loader" \
  -F "file=@${ROOT_DIR}/datasets/followup.csv")"

if [[ "$code" == "200" ]]; then
  echo "followup import completed"
elif [[ "$code" == "409" ]]; then
  echo "followup import already exists"
else
  cat /tmp/sdq-growth-followup-import.json >&2
  fail "followup import failed with HTTP ${code}"
fi

