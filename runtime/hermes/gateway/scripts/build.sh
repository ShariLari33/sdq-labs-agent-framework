#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(gateway_repo_root)"
gateway_prepare_env "$REPO_ROOT"
gateway_require_env "$(gateway_env_file "$REPO_ROOT")"
gateway_compose "$REPO_ROOT" build
