#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(gateway_repo_root)"
gateway_require_env "$(gateway_env_file "$REPO_ROOT")"

curl --fail --silent --show-error --max-time 5 http://localhost:3100/api/health >/dev/null
echo "OK: Paperclip health"

curl --fail --silent --show-error --max-time 5 http://localhost:8000/health >/dev/null
echo "OK: SDQ API health"

"$SCRIPT_DIR/health.sh"

gateway_compose "$REPO_ROOT" exec -T hermes-gateway curl --fail --silent --show-error --max-time 5 http://api:8000/health >/dev/null
echo "OK: Hermes Gateway can reach SDQ API at http://api:8000"

gateway_compose "$REPO_ROOT" exec -T hermes-gateway test -f /home/hermes/AGENTS.md
gateway_compose "$REPO_ROOT" exec -T hermes-gateway test -f /home/hermes/skills/google-ads-performance-analysis/SKILL.md
gateway_compose "$REPO_ROOT" exec -T hermes-gateway test -x /home/hermes/scripts/test-performance-summary.sh
echo "OK: isolated workspace/instructions/skill/scripts mounted"

docker volume inspect sdq-hermes-gateway_sdq_hermes_gateway_state >/dev/null
echo "OK: Hermes state volume exists"

docker exec sdq-paperclip-server-1 curl --fail --silent --show-error --max-time 10 \
  -H "Authorization: Bearer ${API_SERVER_KEY}" \
  http://hermes-gateway:8642/health >/dev/null
echo "OK: Paperclip container can reach Hermes Gateway at http://hermes-gateway:8642"

if git -C "$REPO_ROOT" ls-files runtime/hermes/gateway/.env .local backups | grep . >/dev/null 2>&1; then
  echo "A local env/state/backup path is tracked by Git." >&2
  exit 1
fi
echo "OK: no Hermes Gateway secrets/state tracked by Git"
