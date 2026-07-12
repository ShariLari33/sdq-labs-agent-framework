#!/usr/bin/env bash
set -euo pipefail

SDQ_API_BASE_URL="${SDQ_API_BASE_URL:-http://localhost:8000}"

curl --fail --silent --show-error --max-time 5 "$SDQ_API_BASE_URL/health" >/dev/null
echo "SDQ API health OK at $SDQ_API_BASE_URL/health"
