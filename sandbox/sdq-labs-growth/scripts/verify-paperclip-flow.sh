#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi
if [[ -f "${REPO_ROOT}/runtime/hermes/gateway/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/runtime/hermes/gateway/.env"
  set +a
fi

export PAPERCLIP_API_BASE_URL="${PAPERCLIP_API_BASE_URL:-http://localhost:3100/api}"
python3 -m packages.paperclip.sandbox_bootstrap verify
