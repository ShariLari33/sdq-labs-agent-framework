#!/usr/bin/env bash
set -euo pipefail

if [ ! -f /etc/os-release ] || ! grep -qi ubuntu /etc/os-release; then
  echo "verify-oracle currently supports Ubuntu only." >&2
  exit 1
fi

command -v docker >/dev/null
docker compose version >/dev/null

if [ ! -f .env.production ]; then
  echo "Missing .env.production." >&2
  exit 1
fi

if [ ! -f docker-compose.production.yml ]; then
  echo "Production compose is not implemented yet; see recovery/ORACLE_RECOVERY.md." >&2
  exit 1
fi

docker compose --env-file .env.production -f docker-compose.production.yml config >/dev/null
echo "Oracle production scaffold verification passed."
