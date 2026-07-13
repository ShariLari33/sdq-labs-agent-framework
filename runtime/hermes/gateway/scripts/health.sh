#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(gateway_repo_root)"
gateway_require_env "$(gateway_env_file "$REPO_ROOT")"

for _ in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 5 \
    -H "Authorization: Bearer ${API_SERVER_KEY}" \
    "http://localhost:${HERMES_GATEWAY_PORT}/health" >/dev/null 2>&1; then
    echo "Hermes Gateway health OK at http://localhost:${HERMES_GATEWAY_PORT}/health"
    exit 0
  fi
  sleep 2
done

curl --fail --silent --show-error --max-time 5 \
  -H "Authorization: Bearer ${API_SERVER_KEY}" \
  "http://localhost:${HERMES_GATEWAY_PORT}/health" >/dev/null
