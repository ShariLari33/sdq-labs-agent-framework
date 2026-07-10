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

paperclip_compose "$REPO_ROOT" "$COMPOSE_FILE" "$ENV_FILE" logs -f
