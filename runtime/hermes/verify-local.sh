#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$REPO_ROOT/.local/hermes/venv"
HERMES_BIN="$VENV_DIR/bin/hermes"
HERMES_WRAPPER="$REPO_ROOT/runtime/hermes/hermes-local.sh"
WORKSPACE_DIR="$REPO_ROOT/runtime/hermes/google-ads-agent/workspace"
AGENTS_FILE="$REPO_ROOT/runtime/hermes/google-ads-agent/AGENTS.md"
SKILL_FILE="$REPO_ROOT/runtime/hermes/google-ads-agent/skills/google-ads-performance-analysis/SKILL.md"
SDQ_API_BASE_URL="${SDQ_API_BASE_URL:-http://localhost:8000}"
PAPERCLIP_PUBLIC_URL="${PAPERCLIP_PUBLIC_URL:-http://localhost:3100}"

if [ ! -x "$HERMES_BIN" ]; then
  echo "Hermes command was not found in $VENV_DIR. Run: make hermes-install" >&2
  exit 1
fi

if [ ! -x "$HERMES_WRAPPER" ]; then
  echo "Hermes wrapper is not executable: $HERMES_WRAPPER" >&2
  exit 1
fi

"$HERMES_BIN" --version >/dev/null
"$HERMES_WRAPPER" --version >/dev/null

curl --fail --silent --show-error --max-time 5 "$SDQ_API_BASE_URL/health" >/dev/null
curl --fail --silent --show-error --max-time 5 "$PAPERCLIP_PUBLIC_URL/api/health" >/dev/null
curl --fail --silent --show-error --max-time 10 "$SDQ_API_BASE_URL/performance-data/demo-partner-a/google-ads/summary" >/dev/null

test -d "$WORKSPACE_DIR"
test -f "$AGENTS_FILE"
test -f "$SKILL_FILE"

if git -C "$REPO_ROOT" ls-files runtime/hermes/.env runtime/hermes/.env.local .local .local/hermes/venv | grep . >/dev/null 2>&1; then
  echo "A local Hermes env/secret path is tracked by Git. Check .gitignore." >&2
  exit 1
fi

echo "Hermes executable OK: $HERMES_BIN"
echo "Hermes wrapper OK: $HERMES_WRAPPER"
echo "Hermes version:"
"$HERMES_BIN" --version
echo "SDQ API health OK at $SDQ_API_BASE_URL/health."
echo "SDQ demo summary OK."
echo "Paperclip health OK at $PAPERCLIP_PUBLIC_URL/api/health."
echo "Workspace OK: $WORKSPACE_DIR"
echo "No obvious Hermes local secrets are tracked by Git."
