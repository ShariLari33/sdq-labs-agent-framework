# Oracle Recovery And Future Production Deployment

Oracle production deployment is planned, not fully implemented. `bootstrap-oracle.sh` is a safe scaffold and will stop until production Compose and `.env.production` exist.

## Recommended Minimum VM

- Ubuntu LTS
- 2 vCPU minimum, 4 vCPU preferred
- 8 GB RAM minimum
- 80 GB boot disk minimum
- Separate block volume for database backups if possible

## Implemented Now

- `.env.production.example`
- Ubuntu-only bootstrap guard
- Docker/Compose validation
- production env presence validation
- no automatic provider-secret generation
- no public Postgres exposure in current local Paperclip override

## Future Work Required

- `docker-compose.production.yml`
- reverse proxy configuration, likely Caddy
- domain/DNS configuration
- TLS automation
- production volume layout
- startup service configuration
- off-server backup upload
- monitoring and alerts
- Oracle Hermes installation path and service account policy

## Fresh Oracle Steps

1. Provision Ubuntu VM.
2. Add SSH keys and disable password login where appropriate.
3. Configure Oracle security list/firewall:
   - 22 SSH from trusted IPs
   - 80/443 public through reverse proxy
   - do not expose Postgres ports publicly
4. Install Docker Engine and Compose plugin from Docker's Ubuntu docs.
5. Clone repository:

```bash
git clone https://github.com/ShariLari33/sdq-labs-agent-framework.git
cd sdq-labs-agent-framework
cp .env.production.example .env.production
```

6. Fill `.env.production` from a password manager.
7. Configure DNS and reverse proxy.
8. Validate:

```bash
make bootstrap-oracle
make verify-oracle
```

Today these commands will report missing production Compose until that deployment file is implemented.

Hermes on Oracle should use the same Dockerized gateway architecture used locally:

```text
Paperclip container -> Hermes Gateway container -> SDQ API container
```

Only domains, HTTPS, production secrets, and persistent production volumes should differ. The gateway should remain private to the Docker network or a private overlay network; do not expose port `8642` publicly.
