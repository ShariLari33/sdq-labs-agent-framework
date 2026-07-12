#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/tmp/diagnostics-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT_DIR"

git -C "$REPO_ROOT" status --short --branch > "$OUT_DIR/git-status.txt" 2>&1 || true
docker ps > "$OUT_DIR/docker-ps.txt" 2>&1 || true
docker volume ls > "$OUT_DIR/docker-volumes.txt" 2>&1 || true
curl -fsS http://localhost:8000/health > "$OUT_DIR/sdq-health.json" 2>&1 || true
curl -fsS http://localhost:3100/api/health > "$OUT_DIR/paperclip-health.json" 2>&1 || true
docker logs --tail 200 sdq-api > "$OUT_DIR/sdq-api.log" 2>&1 || true
docker logs --tail 200 sdq-paperclip-server-1 > "$OUT_DIR/paperclip-server.log" 2>&1 || true

echo "Diagnostics collected in $OUT_DIR"
echo "Review before sharing; logs may contain operational details."
