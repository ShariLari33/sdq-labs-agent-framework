#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$REPO_ROOT/.local/hermes/venv"
HERMES_BIN="$VENV_DIR/bin/hermes"

if [ ! -x "$HERMES_BIN" ]; then
  echo "Hermes executable not found at $HERMES_BIN. Run: make hermes-install" >&2
  exit 127
fi

mkdir -p "$REPO_ROOT/.local/hermes/state" "$REPO_ROOT/.local/hermes/config"

export VIRTUAL_ENV="$VENV_DIR"
export PATH="$VENV_DIR/bin:$PATH"
export HERMES_HOME="${HERMES_HOME:-$REPO_ROOT/.local/hermes/state}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$REPO_ROOT/.local/hermes/config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$REPO_ROOT/.local/hermes/cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$REPO_ROOT/.local/hermes/data}"

exec "$HERMES_BIN" "$@"
