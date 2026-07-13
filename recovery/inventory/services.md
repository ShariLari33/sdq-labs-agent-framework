# Services Inventory

| Service | Purpose | Scope | Source | Startup | Health |
|---|---|---|---|---|---|
| `postgres` / `sdq-postgres` | SDQ PostgreSQL with pgvector | local now, production future | `docker-compose.yml` | `docker compose up -d` | `pg_isready`, pgvector query |
| `api` / `sdq-api` | SDQ FastAPI tenant data/tool layer | local now, production future | `apps/api/main.py`, `docker-compose.yml` | `docker compose up -d --build` | `GET /health` on 8000 |
| `adminer` / `sdq-adminer` | local DB admin UI | local only | `docker-compose.yml` | `docker compose up -d` | browser on 8080 |
| `server` / `sdq-paperclip-server-1` | Paperclip control plane | local now, production future | official Paperclip clone in `.local/platform/paperclip-source` | `make paperclip-start` | `GET /api/health` on 3100 |
| `db` / `sdq-paperclip-db-1` | separate Paperclip PostgreSQL | local now, production future | official Paperclip compose plus override | `make paperclip-start` | `pg_isready` |
| Hermes CLI | local agent runtime for Paperclip `hermes_local` | local now, production future | PyPI `hermes-agent` | `make hermes-install` | `.local/hermes/venv/bin/hermes --version` |
| `hermes-gateway` / `sdq-hermes-gateway` | Hermes API runtime for Paperclip `hermes_gateway` | local now, production future | `runtime/hermes/gateway/docker-compose.yml` | `make hermes-gateway-start` | `GET /health` on 8642 with bearer token |

Future/planned: Oracle production Compose, reverse proxy, TLS, monitoring, off-server backups.
