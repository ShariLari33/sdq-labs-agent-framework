# Paperclip Local Control Plane

This directory prepares SDQ Labs to run the official Paperclip control plane locally, next to the SDQ API. Paperclip remains an external platform: its source is cloned into `.local/platform/paperclip-source`, it runs from the official Docker Compose configuration, and it uses its own Postgres database.

The SDQ FastAPI backend and SDQ Postgres schema are not modified by this setup.

## Requirements

- Docker and Docker Compose
- Git
- OpenSSL
- SDQ API running on `http://localhost:8000`

## Files

- `platform/paperclip/.env.example`: local configuration template
- `platform/paperclip/.env`: generated local secrets, ignored by Git
- `.local/platform/paperclip-source`: official Paperclip clone, ignored by Git
- `platform/paperclip/docker-compose.override.yml`: SDQ-local override for the official compose stack

## Start

From the repository root:

```bash
make paperclip-start
```

The first start clones `https://github.com/paperclipai/paperclip.git`, creates `platform/paperclip/.env`, generates local secrets, starts Paperclip and its own Postgres database, then waits for `http://localhost:3100/api/health`.

Open:

```text
http://localhost:3100
```

Create the first admin account in the browser. The deployment is configured as `authenticated` and `private`.

## Stop And Logs

```bash
make paperclip-stop
make paperclip-logs
make paperclip-status
```

Stopping preserves Paperclip volumes. The setup does not expose the Paperclip database port publicly.

## Verify

```bash
make paperclip-status
```

The verifier checks Paperclip health on port `3100`, SDQ health on port `8000`, separate database containers, and whether obvious Paperclip secrets are accidentally tracked by Git.

## Configuration

Edit `platform/paperclip/.env` for local configuration. Keep API keys empty unless you intentionally want Paperclip adapters to call providers. Do not commit this file.

SDQ integration is prepared with:

```text
SDQ_API_BASE_URL=http://host.docker.internal:8000
SDQ_INTERNAL_API_TOKEN=<generated local token>
```

Hermes, Paperclip agents, and live SDQ integration are intentionally left for later. Do not use real customer data in this local setup.
