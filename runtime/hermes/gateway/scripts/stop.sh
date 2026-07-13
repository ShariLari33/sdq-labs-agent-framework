#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(gateway_repo_root)"
gateway_require_env "$(gateway_env_file "$REPO_ROOT")"
gateway_compose "$REPO_ROOT" stop
echo "Stopped Hermes Gateway. State volume was preserved."
