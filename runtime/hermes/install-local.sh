#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$REPO_ROOT/.local/hermes/venv"
STATE_DIR="$REPO_ROOT/.local/hermes/state"
CONFIG_DIR="$REPO_ROOT/.local/hermes/config"
HERMES_BIN="$VENV_DIR/bin/hermes"

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
  then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3.11+ is required to install Hermes locally." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

mkdir -p "$STATE_DIR" "$CONFIG_DIR"

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade hermes-agent

echo "Hermes virtual environment: $VENV_DIR"
if [ -x "$HERMES_BIN" ]; then
  "$HERMES_BIN" --version
elif [ -x "$VENV_DIR/bin/hermes-agent" ]; then
  "$VENV_DIR/bin/hermes-agent" --version || true
else
  echo "Hermes installation did not expose a hermes executable in $VENV_DIR/bin." >&2
  "$VENV_DIR/bin/python" -m pip show hermes-agent || true
  exit 1
fi

echo "Hermes executable: $HERMES_BIN"
echo "Hermes state directory: $STATE_DIR"
echo "Hermes config directory: $CONFIG_DIR"
echo "Provider API keys were not configured."
