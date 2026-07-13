#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[sdq-hermes-gateway] $*"
}

if [ -z "${API_SERVER_KEY:-}" ]; then
  echo "API_SERVER_KEY is required. Set it in runtime/hermes/gateway/.env." >&2
  exit 1
fi

export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-8642}"
export NO_COLOR="${NO_COLOR:-1}"
export HERMES_HOME="${HERMES_HOME:-/home/hermes/.hermes}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/home/hermes/.config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/home/hermes/.cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-/home/hermes/.local/share}"

if [ "$API_SERVER_ENABLED" != "true" ]; then
  echo "API_SERVER_ENABLED must be true for Paperclip hermes_gateway." >&2
  exit 1
fi

mkdir -p "$HERMES_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
chmod 0700 "$HERMES_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" || true

log "Hermes version: $(hermes --version 2>&1 | head -n 1)"
log "workspace=$(pwd)"
log "API_SERVER_HOST=${API_SERVER_HOST}"
log "API_SERVER_PORT=${API_SERVER_PORT}"
log "SDQ_API_BASE_URL=${SDQ_API_BASE_URL:-unset}"
log "Paperclip API URL=${PAPERCLIP_API_URL:-unset}"

exec hermes gateway run --replace --accept-hooks "$@"
