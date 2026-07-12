#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

failures=0
check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "OK: $name"
  else
    echo "FAIL: $name" >&2
    failures=$((failures + 1))
  fi
}

check "git worktree readable" git status --short
check "docker daemon reachable" docker info
check "SDQ API health" curl --fail --silent --show-error --max-time 5 http://localhost:8000/health
check "Paperclip health" curl --fail --silent --show-error --max-time 5 http://localhost:3100/api/health
check "SDQ postgres container" docker inspect sdq-postgres
check "Paperclip postgres container" docker inspect sdq-paperclip-db-1
check "Hermes executable" test -x "$REPO_ROOT/.local/hermes/venv/bin/hermes"
check "AGENTS.md exists" test -f "$REPO_ROOT/runtime/hermes/google-ads-agent/AGENTS.md"
check "SKILL.md exists" test -f "$REPO_ROOT/runtime/hermes/google-ads-agent/skills/google-ads-performance-analysis/SKILL.md"

echo "Checking pgvector availability..."
if docker exec sdq-postgres psql -U sdq -d sdq_agents -tAc "SELECT 1 FROM pg_extension WHERE extname='vector';" | grep -q 1; then
  echo "OK: pgvector extension installed"
else
  echo "FAIL: pgvector extension not found" >&2
  failures=$((failures + 1))
fi

echo "Checking expected ports..."
for port in 5432 8000 8080 3100; do
  if docker ps --format '{{.Ports}}' | grep -q ":$port->"; then
    echo "OK: port $port is bound by an expected local service"
  else
    echo "FAIL: port $port is not bound" >&2
    failures=$((failures + 1))
  fi
done

echo "Checking Git-tracked secrets..."
tracked_secret_files="$(git ls-files | grep -E '(^|/)\.env$|(^|/)\.env\.|\.pem$|\.key$|\.dump$|\.sql(\.gz)?$' | grep -v -E '(^|/)\.env(\.production)?\.example$|^packages/database/init\.sql$' || true)"
if [ -n "$tracked_secret_files" ]; then
  echo "FAIL: Git is tracking env/key/dump-looking files" >&2
  echo "$tracked_secret_files" >&2
  failures=$((failures + 1))
else
  echo "OK: no obvious env/key/dump files tracked"
fi

if git grep -n -E 'sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY' -- . ':!recovery/**' >/tmp/sdq-secret-scan.txt 2>/dev/null; then
  echo "FAIL: obvious secret pattern found in tracked files" >&2
  cat /tmp/sdq-secret-scan.txt >&2
  failures=$((failures + 1))
else
  echo "OK: no obvious provider/private-key patterns found"
fi

if [ "$failures" -ne 0 ]; then
  echo "$failures verification check(s) failed." >&2
  exit 1
fi

echo "Local recovery verification passed."
