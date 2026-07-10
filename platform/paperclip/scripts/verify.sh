#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(paperclip_repo_root)"
SOURCE_DIR="$REPO_ROOT/.local/platform/paperclip-source"
ENV_FILE="$REPO_ROOT/platform/paperclip/.env"

paperclip_env_load "$ENV_FILE"
COMPOSE_FILE="$(paperclip_compose_file "$SOURCE_DIR")"

echo "Checking Paperclip health..."
curl -fsS "http://localhost:3100/api/health" >/dev/null

echo "Checking SDQ API health..."
curl -fsS "http://localhost:8000/health" >/dev/null

echo "Checking Paperclip compose project containers..."
paperclip_compose "$REPO_ROOT" "$COMPOSE_FILE" "$ENV_FILE" ps

if ! paperclip_compose "$REPO_ROOT" "$COMPOSE_FILE" "$ENV_FILE" ps db >/dev/null 2>&1; then
  echo "Paperclip database container was not found in the sdq-paperclip compose project." >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -Ev '^sdq-paperclip-' | grep -Ei 'sdq.*postgres|postgres|db' >/dev/null 2>&1; then
  echo "Could not find an SDQ/Postgres-looking container. Is docker compose up -d running for SDQ?" >&2
  exit 1
fi

if git -C "$REPO_ROOT" ls-files platform/paperclip/.env .local | grep . >/dev/null 2>&1; then
  echo "A local Paperclip secret/source path is tracked by Git. Check .gitignore." >&2
  exit 1
fi

echo "Paperclip health OK on port 3100."
echo "SDQ health OK on port 8000."
echo "Paperclip and SDQ database containers are separate."
echo "No obvious Paperclip local secrets are tracked by Git."
