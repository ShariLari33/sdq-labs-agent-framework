# Backup And Restore

Backups cover:

- SDQ PostgreSQL database `sdq_agents`
- Paperclip PostgreSQL database `paperclip`
- non-secret runtime metadata
- agent and skill files already stored in Git

Backups do not include plaintext `.env` files by default. Secrets must be stored separately in a password manager.

## Create Local Backup

```bash
make backup
```

This creates `backups/local-<timestamp>/` with:

- `sdq_agents.dump`
- `paperclip.dump`
- `repo-runtime-metadata.tar.gz`
- `manifest.txt`

Encrypt and copy backups off-device/off-server. A future production backup job should upload encrypted archives to external storage.

## Restore Dry Run

```bash
make restore BACKUP=backups/local-YYYYMMDDTHHMMSSZ
```

## Confirmed Restore

Stop application writers first. Then:

```bash
CONFIRM_RESTORE=yes ALLOW_RUNNING_DATABASES=yes ./recovery/scripts/restore.sh backups/local-YYYYMMDDTHHMMSSZ
make verify-local
```

Restore is deliberately explicit because it overwrites database contents.

## Retention

Suggested minimum:

- local development: keep the last 7 successful backups
- production: daily for 30 days, weekly for 12 weeks, monthly for 12 months
- always keep at least one off-server encrypted backup
