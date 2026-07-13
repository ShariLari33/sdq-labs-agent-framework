#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(gateway_repo_root)"
gateway_prepare_env "$REPO_ROOT"
gateway_require_env "$(gateway_env_file "$REPO_ROOT")"

if ! docker network inspect sdq-labs-agent-framework_default >/dev/null 2>&1; then
  echo "Missing SDQ Docker network. Start SDQ first: docker compose up -d" >&2
  exit 1
fi

if ! docker network inspect sdq-paperclip_default >/dev/null 2>&1; then
  echo "Missing Paperclip Docker network. Start Paperclip first: make paperclip-start" >&2
  exit 1
fi

gateway_compose "$REPO_ROOT" up -d --build
"$SCRIPT_DIR/health.sh"
echo "Hermes Gateway is running at http://localhost:${HERMES_GATEWAY_PORT}"
echo "Paperclip apiBaseUrl from inside Docker: http://hermes-gateway:8642"
