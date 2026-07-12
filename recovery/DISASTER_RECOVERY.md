# Disaster Recovery

## New Laptop

- Impact: local runtime unavailable.
- First action: clone GitHub repository.
- Recovery source: GitHub, password manager, latest backup.
- Steps: follow `NEW_DEVICE_SETUP.md`.
- Validation: `make verify-local`.
- Credential rotation: not required unless laptop was lost or compromised.

## Lost Laptop

- Impact: local secrets and data may be exposed.
- First action: rotate GitHub, provider, Paperclip, SDQ internal, and SSH credentials.
- Recovery source: GitHub, password manager, off-device backup.
- Steps: recover on new device, restore only trusted backups.
- Validation: health checks plus audit of Paperclip users/tokens.
- Credential rotation: required.

## Corrupted Local Docker Volume

- Impact: local DB/app state unavailable.
- First action: stop writers and collect diagnostics.
- Recovery source: latest local/off-device backup.
- Steps: restore using `restore.sh` with explicit confirmation.
- Validation: `make verify-local`.
- Credential rotation: not usually required.

## Oracle VM Failure

- Impact: production unavailable.
- First action: provision replacement VM.
- Recovery source: GitHub, password manager, off-server backups.
- Steps: follow `ORACLE_RECOVERY.md`, restore databases, restore proxy config.
- Validation: production health checks.
- Credential rotation: required if compromise is possible.

## Database Corruption

- Impact: SDQ or Paperclip state unreliable.
- First action: stop application writers.
- Recovery source: latest known-good dump.
- Steps: restore affected database, then run health checks.
- Validation: application workflows and DB integrity checks.
- Credential rotation: not required unless caused by compromise.

## Accidental Skill Version Change

- Impact: agent behavior may regress.
- First action: stop approving new runs using that skill.
- Recovery source: Git history and skill_versions history in SDQ DB.
- Steps: restore prior approved skill version through API/admin process.
- Validation: skill integrity endpoint and dry run.
- Credential rotation: not required.

## Leaked Credential

- Impact: external access risk.
- First action: revoke/rotate the credential at provider.
- Recovery source: password manager.
- Steps: update local/server env files, restart affected service.
- Validation: health checks and audit logs.
- Credential rotation: required.

## Lost Domain Or DNS Access

- Impact: production public endpoints unreachable.
- First action: regain registrar/DNS access or move to backup domain.
- Recovery source: registrar account, DNS records, reverse proxy config.
- Steps: repoint DNS, renew TLS, update public URLs.
- Validation: HTTPS health endpoints.
- Credential rotation: required if account compromise is possible.

## GitHub Temporarily Unavailable

- Impact: fresh deploys blocked if no clone exists.
- First action: use existing local/server checkout.
- Recovery source: local clone, recent archive, backup.
- Steps: avoid destructive changes, wait for GitHub recovery.
- Validation: compare commit once GitHub returns.
- Credential rotation: not required.

## Paperclip Database Unavailable

- Impact: control plane unavailable.
- First action: inspect `sdq-paperclip-db-1`.
- Recovery source: Paperclip dump and `sdq-paperclip_pgdata`.
- Steps: restore Paperclip DB if needed.
- Validation: `curl http://localhost:3100/api/health`.
- Credential rotation: not required.

## Hermes Runtime Unavailable

- Impact: local agent execution unavailable.
- First action: run `make hermes-install`.
- Recovery source: PyPI `hermes-agent`, Git instructions.
- Steps: recreate `.local/hermes/venv`.
- Validation: `.local/hermes/venv/bin/hermes --version`.
- Credential rotation: not required unless Hermes config leaked.
