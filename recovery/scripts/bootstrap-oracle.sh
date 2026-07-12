#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f /etc/os-release ] || ! grep -qi ubuntu /etc/os-release; then
  echo "bootstrap-oracle currently supports Ubuntu only." >&2
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  echo "Run as a non-root sudo user, not root." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "Docker Engine and the Compose plugin are required before production bootstrap." >&2
  echo "Install from Docker's Ubuntu instructions, then rerun." >&2
  exit 1
fi

if [ ! -f .env.production ]; then
  echo "Missing .env.production. Copy .env.production.example and fill production secrets first." >&2
  exit 1
fi

if [ ! -f docker-compose.production.yml ]; then
  echo "Production compose is not implemented yet: docker-compose.production.yml is missing." >&2
  echo "No services were started." >&2
  exit 1
fi

docker compose --env-file .env.production -f docker-compose.production.yml config >/dev/null
echo "Production compose validated. Starting services..."
docker compose --env-file .env.production -f docker-compose.production.yml up -d
