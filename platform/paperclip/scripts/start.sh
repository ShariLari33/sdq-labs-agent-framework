#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(paperclip_repo_root)"
PAPERCLIP_DIR="$REPO_ROOT/platform/paperclip"
SOURCE_DIR="$REPO_ROOT/.local/platform/paperclip-source"
ENV_FILE="$PAPERCLIP_DIR/.env"
ENV_EXAMPLE="$PAPERCLIP_DIR/.env.example"

"$SCRIPT_DIR/clone-or-update.sh"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required to generate local Paperclip secrets." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  auth_secret="$(openssl rand -hex 32)"
  db_password="$(openssl rand -hex 24)"
  sdq_token="$(openssl rand -hex 32)"

  tmp_file="$(mktemp)"
  sed \
    -e "s/^BETTER_AUTH_SECRET=.*/BETTER_AUTH_SECRET=$auth_secret/" \
    -e "s/^PAPERCLIP_POSTGRES_PASSWORD=.*/PAPERCLIP_POSTGRES_PASSWORD=$db_password/" \
    -e "s/^SDQ_INTERNAL_API_TOKEN=.*/SDQ_INTERNAL_API_TOKEN=$sdq_token/" \
    "$ENV_FILE" > "$tmp_file"
  mv "$tmp_file" "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  echo "Created $ENV_FILE with generated local secrets. Provider API keys were left empty."
fi

paperclip_env_load "$ENV_FILE"

: "${PAPERCLIP_PUBLIC_URL:?PAPERCLIP_PUBLIC_URL is required}"
: "${PAPERCLIP_DEPLOYMENT_MODE:?PAPERCLIP_DEPLOYMENT_MODE is required}"
: "${PAPERCLIP_DEPLOYMENT_EXPOSURE:?PAPERCLIP_DEPLOYMENT_EXPOSURE is required}"
: "${BETTER_AUTH_SECRET:?BETTER_AUTH_SECRET is required}"
: "${PAPERCLIP_POSTGRES_USER:?PAPERCLIP_POSTGRES_USER is required}"
: "${PAPERCLIP_POSTGRES_PASSWORD:?PAPERCLIP_POSTGRES_PASSWORD is required}"
: "${PAPERCLIP_POSTGRES_DB:?PAPERCLIP_POSTGRES_DB is required}"
: "${SDQ_API_BASE_URL:?SDQ_API_BASE_URL is required}"

if [ "$PAPERCLIP_DEPLOYMENT_MODE" != "authenticated" ]; then
  echo "PAPERCLIP_DEPLOYMENT_MODE must be authenticated for this local control plane." >&2
  exit 1
fi

if [ "$PAPERCLIP_DEPLOYMENT_EXPOSURE" != "private" ]; then
  echo "PAPERCLIP_DEPLOYMENT_EXPOSURE must be private for this local control plane." >&2
  exit 1
fi

COMPOSE_FILE="$(paperclip_compose_file "$SOURCE_DIR")"
echo "Using official Paperclip compose: $COMPOSE_FILE"

paperclip_compose "$REPO_ROOT" "$COMPOSE_FILE" "$ENV_FILE" up -d --build
paperclip_wait_for_health "http://localhost:3100/api/health"

commit="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"
echo "Paperclip is running at $PAPERCLIP_PUBLIC_URL"
echo "Deployment mode: $PAPERCLIP_DEPLOYMENT_MODE/$PAPERCLIP_DEPLOYMENT_EXPOSURE"
echo "Official Paperclip commit: $commit"
echo "Open $PAPERCLIP_PUBLIC_URL in a browser to create the first admin account."
