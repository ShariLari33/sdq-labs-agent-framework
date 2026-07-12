#!/usr/bin/env bash
set -euo pipefail

tenant_slug="${1:-}"
SDQ_API_BASE_URL="${SDQ_API_BASE_URL:-http://localhost:8000}"
SDQ_INTERNAL_API_TOKEN="${SDQ_INTERNAL_API_TOKEN:-}"

if [ -z "$tenant_slug" ]; then
  echo "Usage: $0 <tenant_slug>" >&2
  exit 2
fi

url="$SDQ_API_BASE_URL/performance-data/$tenant_slug/google-ads/summary"

if [ -n "$SDQ_INTERNAL_API_TOKEN" ]; then
  curl --fail --silent --show-error --max-time 10 \
    -H "Authorization: Bearer $SDQ_INTERNAL_API_TOKEN" \
    "$url"
else
  curl --fail --silent --show-error --max-time 10 "$url"
fi
