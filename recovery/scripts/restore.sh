#!/usr/bin/env bash
set -euo pipefail

backup_dir="${1:-}"
CONFIRM="${CONFIRM_RESTORE:-no}"
ALLOW_RUNNING="${ALLOW_RUNNING_DATABASES:-no}"

if [ -z "$backup_dir" ]; then
  echo "Usage: CONFIRM_RESTORE=yes ALLOW_RUNNING_DATABASES=yes $0 <backup-dir>" >&2
  echo "Default is dry-run. Set CONFIRM_RESTORE=yes only after reading recovery/BACKUP_AND_RESTORE.md." >&2
  exit 2
fi

if [ ! -f "$backup_dir/manifest.txt" ]; then
  echo "Backup manifest not found: $backup_dir/manifest.txt" >&2
  exit 1
fi

echo "Restore plan for $backup_dir:"
echo "1. Verify manifest and dump files."
echo "2. Stop application writers."
echo "3. Restore SDQ PostgreSQL from sdq_agents.dump."
echo "4. Restore Paperclip PostgreSQL from paperclip.dump."
echo "5. Restore non-secret runtime metadata only if needed."
echo "6. Run health checks."

test -f "$backup_dir/sdq_agents.dump"
test -f "$backup_dir/paperclip.dump"

if [ "$CONFIRM" != "yes" ]; then
  echo "Dry-run complete. No data was changed. Set CONFIRM_RESTORE=yes to proceed." >&2
  exit 0
fi

if [ "$ALLOW_RUNNING" != "yes" ]; then
  echo "Refusing restore while databases may be running. Set ALLOW_RUNNING_DATABASES=yes only after stopping writers." >&2
  exit 1
fi

echo "Confirmed restore. This will overwrite database contents."
docker exec -i sdq-postgres pg_restore -U sdq -d sdq_agents --clean --if-exists < "$backup_dir/sdq_agents.dump"
docker exec -i sdq-paperclip-db-1 pg_restore -U paperclip -d paperclip --clean --if-exists < "$backup_dir/paperclip.dump"
echo "Restore completed. Run: make verify-local"
