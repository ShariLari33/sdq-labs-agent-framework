# Hermes Gateway Runtime

This runs Hermes Agent as a separate Dockerized API server for Paperclip's built-in `hermes_gateway` adapter. It avoids the container-boundary problem where Paperclip in Linux Docker cannot reliably execute a macOS host path.

## Discovered Paperclip Integration

- Adapter type: `hermes_gateway`
- Required adapter config fields:
  - `apiBaseUrl`
  - `apiKey`
- Optional adapter config fields:
  - `paperclipApiUrl`
  - `sessionKeyStrategy`
  - `timeoutSec`
  - `eventReconnectMs`
  - `headers`
  - `instructions`
- Hermes gateway health endpoint: `GET /health`
- Auth: `Authorization: Bearer <API_SERVER_KEY>`
- Run API used by Paperclip:
  - `POST /v1/runs`
  - `GET /v1/runs/{run_id}/events`
  - `GET /v1/runs/{run_id}`
  - `POST /v1/runs/{run_id}/stop`

Paperclip's source documents `Invite External Agent` as an onboarding flow for agent-only invites. It creates a join request with `adapterType: "hermes_gateway"` and an `agentDefaultsPayload` containing `apiBaseUrl`, `apiKey`, `sessionKeyStrategy`, and `timeoutSec`. Local MVP can also edit an existing agent and set the same adapter fields manually in the UI.

## Local URLs

- Host health URL: `http://localhost:8642/health`
- Paperclip container to Hermes URL: `http://hermes-gateway:8642`
- Hermes container to SDQ API URL: `http://api:8000`
- Hermes container to Paperclip API URL: `http://server:3100/api`

## Paperclip Adapter Values

Use these values in Paperclip for the local MVP:

- Adapter type: `hermes_gateway`
- API base URL: `http://hermes-gateway:8642`
- API key: value of `API_SERVER_KEY` in `runtime/hermes/gateway/.env`
- Paperclip API URL: `http://server:3100/api`
- Session key strategy: `issue`
- Timeout seconds: `1800`
- Event reconnect ms: `2000`

Do not paste `API_SERVER_KEY` into prompts, task descriptions, comments, logs, or committed files.

## Commands

```bash
make hermes-gateway-build
make hermes-gateway-start
make hermes-gateway-health
make hermes-gateway-verify
make hermes-gateway-logs
make hermes-gateway-stop
```

The first start creates `runtime/hermes/gateway/.env` from `.env.example` and generates a local development `API_SERVER_KEY` without printing it.

## Isolation

The container mounts only:

- `runtime/hermes/google-ads-agent/workspace`
- `runtime/hermes/google-ads-agent/AGENTS.md`
- `runtime/hermes/google-ads-agent/skills`
- `runtime/hermes/google-ads-agent/scripts`

It does not mount the full repository, `.env` files, database volumes, SSH keys, or the Paperclip database.
