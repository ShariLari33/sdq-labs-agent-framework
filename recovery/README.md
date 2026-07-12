# Recovery And Setup

This directory is the recovery runbook for SDQ Labs Agent Framework. Git is the source of truth for code, scripts, documentation, agent instructions, and skill markdown. Git is not the source of truth for secrets, database contents, Docker volumes, or runtime state.

Current restore readiness score: 7/10 for local development, 3/10 for Oracle production. Local setup is mostly automated; Oracle production still needs a production Compose/reverse-proxy implementation.

## Quick Local Recovery

```bash
git clone https://github.com/ShariLari33/sdq-labs-agent-framework.git
cd sdq-labs-agent-framework
cp .env.example .env
make bootstrap-local
make verify-local
```

## Before Every Major Deployment

- Code pushed to GitHub.
- Database migrations/schema changes committed.
- Environment templates updated.
- Backup completed and copied off-device/off-server.
- Health checks passing.
- Rollback path documented.

## Before Changing Laptop

- Push all commits.
- Verify no untracked essential files: `git status --short`.
- Export and secure credentials separately in a password manager.
- Create a fresh backup: `make backup`.
- Test recovery instructions on a clean checkout where possible.

## Entry Points

- New macOS device: `recovery/NEW_DEVICE_SETUP.md`
- Local restore: `recovery/LOCAL_RECOVERY.md`
- Oracle Ubuntu future deployment: `recovery/ORACLE_RECOVERY.md`
- Disaster scenarios: `recovery/DISASTER_RECOVERY.md`
- Backups: `recovery/BACKUP_AND_RESTORE.md`
- Secrets: `recovery/SECRETS_CHECKLIST.md`
- Health checks: `recovery/HEALTH_CHECKS.md`

## Inventory

- `recovery/inventory/services.md`
- `recovery/inventory/ports.md`
- `recovery/inventory/volumes.md`
- `recovery/inventory/environment-variables.md`
- `recovery/inventory/external-dependencies.md`
