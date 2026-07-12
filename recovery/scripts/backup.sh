#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODE="${MODE:-local}"
BACKUP_ROOT="${BACKUP_ROOT:-$REPO_ROOT/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$BACKUP_ROOT/$MODE-$timestamp"

mkdir -p "$dest"
chmod 700 "$BACKUP_ROOT" "$dest"

manifest="$dest/manifest.txt"
{
  echo "created_at_utc=$timestamp"
  echo "mode=$MODE"
  echo "repo=$(git -C "$REPO_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
  echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
  echo "includes_plaintext_env=false"
} > "$manifest"

echo "Backing up SDQ PostgreSQL..."
docker exec sdq-postgres pg_dump -U sdq -d sdq_agents -Fc > "$dest/sdq_agents.dump"

echo "Backing up Paperclip PostgreSQL..."
docker exec sdq-paperclip-db-1 pg_dump -U paperclip -d paperclip -Fc > "$dest/paperclip.dump"

echo "Archiving non-secret runtime metadata..."
tar -czf "$dest/repo-runtime-metadata.tar.gz" \
  -C "$REPO_ROOT" \
  --exclude='*.env' \
  --exclude='.env' \
  --exclude='*.log' \
  runtime/hermes \
  platform/paperclip/.env.example \
  .env.example \
  .env.production.example \
  recovery

{
  echo "file=sdq_agents.dump"
  echo "file=paperclip.dump"
  echo "file=repo-runtime-metadata.tar.gz"
} >> "$manifest"

echo "Backup created: $dest"
echo "Encrypt and copy this directory off-device/off-server. Plaintext .env files were not included."
