#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$REPO_ROOT/.local/hermes/venv"

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

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install hermes-agent

echo "Hermes virtual environment: $VENV_DIR"
if [ -x "$VENV_DIR/bin/hermes" ]; then
  "$VENV_DIR/bin/hermes" --version || true
elif [ -x "$VENV_DIR/bin/hermes-agent" ]; then
  "$VENV_DIR/bin/hermes-agent" --version || true
else
  "$VENV_DIR/bin/python" -m pip show hermes-agent
fi

echo "Provider API keys were not configured."
