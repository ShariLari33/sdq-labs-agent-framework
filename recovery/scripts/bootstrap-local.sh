#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

missing=0
need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required tool: $1" >&2
    missing=1
  fi
}

case "$(uname -s)" in
  Darwin) ;;
  *) echo "Warning: bootstrap-local is designed for macOS. Continuing with best effort." >&2 ;;
esac

need git
need docker
need curl
need openssl
need python3

if ! docker compose version >/dev/null 2>&1; then
  echo "Missing Docker Compose plugin. Install Docker Desktop for macOS: https://www.docker.com/products/docker-desktop/" >&2
  missing=1
fi

if [ "$missing" -ne 0 ]; then
  echo "Install missing tools, then rerun: make bootstrap-local" >&2
  echo "macOS basics: xcode-select --install; install Homebrew from https://brew.sh; install Docker Desktop manually." >&2
  exit 1
fi

cd "$REPO_ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created .env from .env.example. Fill provider keys only when needed."
fi

if [ ! -f platform/paperclip/.env ] && [ -f platform/paperclip/.env.example ]; then
  echo "Paperclip .env is missing; paperclip-start will create it with local generated secrets."
fi

echo "Starting SDQ Docker services..."
docker compose up -d --build

echo "Starting Paperclip through existing Makefile target..."
make paperclip-start

echo "Installing Hermes through existing Makefile target..."
make hermes-install

echo "Local bootstrap complete."
echo "Next manual actions:"
echo "- Open http://localhost:3100 and finish/create Paperclip admin if needed."
echo "- Configure a hermes_local agent with command: $REPO_ROOT/runtime/hermes/hermes-local.sh"
echo "- Use working directory: $REPO_ROOT/runtime/hermes/google-ads-agent/workspace"
echo "- Run: make verify-local"
