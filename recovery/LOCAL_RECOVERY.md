# Local Recovery

Use this when the local stack is broken but the repository still exists.

## Standard Recovery

```bash
docker compose up -d --build
make paperclip-start
make hermes-install
make verify-local
```

## If Environment Files Are Missing

```bash
cp .env.example .env
make paperclip-start
```

Paperclip creates `platform/paperclip/.env` from its example and generates development-only local secrets.

## If Docker Volumes Are Corrupt

Do not delete volumes first. Create a backup/diagnostic bundle:

```bash
make diagnostics
make backup
```

If a deliberate restore is needed, follow `BACKUP_AND_RESTORE.md`.

## Local Source Of Truth

- Code/config: GitHub repository.
- SDQ DB: Docker volume `sdq-labs-agent-framework_sdq_postgres_data`.
- Paperclip DB: Docker volume `sdq-paperclip_pgdata`.
- Paperclip app files: Docker volume `sdq-paperclip_paperclip-data`.
- Hermes venv/upstream clones: `.local/`, reproducible from scripts.
