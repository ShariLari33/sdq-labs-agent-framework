# Health Checks

## Local

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:3100/api/health
make paperclip-status
make hermes-verify
make verify-local
```

## SDQ API

- URL: `http://localhost:8000/health`
- Expected: JSON with `status: ok`

## Paperclip

- URL: `http://localhost:3100/api/health`
- Expected: JSON with `status: ok`

## SDQ PostgreSQL

```bash
docker exec sdq-postgres pg_isready -U sdq -d sdq_agents
docker exec sdq-postgres psql -U sdq -d sdq_agents -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

## Paperclip PostgreSQL

```bash
docker exec sdq-paperclip-db-1 pg_isready -U paperclip -d paperclip
```

## Hermes

```bash
.local/hermes/venv/bin/hermes --version
```
