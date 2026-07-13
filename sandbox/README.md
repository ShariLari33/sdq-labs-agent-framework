# SDQ Sandbox

This directory contains synthetic demo environments for the SDQ Labs Agent Framework.

## One-Command Demo

Run:

```bash
make sandbox
```

The command starts Docker, bootstraps the `SDQ Labs Growth Sandbox` tenant, imports synthetic Google Ads datasets, creates baseline/follow-up/validation tasks, runs the task engine, approves demo approvals as `Sharif`, creates performance feedback, approves a learning candidate, creates and approves an evolution proposal, verifies the newest skill version, and prints `SANDBOX READY`.

All data is fictional. Do not use real Google Ads credentials or live customer data.

## Full Paperclip-Controlled Demo

Run:

```bash
make sandbox-full
```

This runs the SDQ sandbox flow, then attempts the Paperclip-controlled bootstrap and verification.

If `PAPERCLIP_OPERATOR_API_TOKEN` is not configured, the Paperclip step exits cleanly as `skipped` and does not modify Paperclip.

## Paperclip Operator Token

Create a Paperclip board/operator API token in the Paperclip UI or CLI with permission to list/create companies, list/create agents, create issues, assign issues, and wake agents.

Store it only in an ignored local file, for example root `.env`:

```bash
PAPERCLIP_API_BASE_URL=http://localhost:3100/api
PAPERCLIP_OPERATOR_API_TOKEN=...
```

Do not put the token in shell history, task descriptions, code, committed files, or command-line arguments. The sandbox scripts read it from environment or ignored `.env` files and send it as:

```text
Authorization: Bearer <token>
```

## SDQ Tenant vs Paperclip Company

The SDQ tenant is the data and execution boundary inside the SDQ API:

```text
sdq-labs-growth-sandbox
```

The Paperclip company is the control-plane workspace:

```text
SDQ Labs Growth Sandbox
```

The sandbox bootstrap links them by task instructions. It does not copy SDQ database records into Paperclip.

## Sandbox Safety

Automatic approvals, automatic evolution approvals, and synthetic data imports are sandbox-only.

The sandbox command temporarily sets:

```bash
SDQ_ENVIRONMENT=sandbox
SDQ_ALLOW_AUTO_APPROVALS=true
SDQ_ALLOW_AUTO_EVOLUTION=true
SDQ_ALLOW_SYNTHETIC_DATA=true
```

Defaults are false. Production refuses to start if auto-approval, auto-evolution, or synthetic-data flags are enabled.

Manual fallback when no Paperclip token exists:

1. Run `make sandbox`.
2. Open Paperclip at `http://localhost:3100`.
3. Create company `SDQ Labs Growth Sandbox`.
4. Assign the registered Hermes Gateway agent.
5. Create an issue titled `Analyse baseline Google Ads performance`.
6. Include the tenant slug `sdq-labs-growth-sandbox` and require approval before external changes.

## Manual Commands

```bash
sandbox/sdq-labs-growth/scripts/bootstrap.sh
sandbox/sdq-labs-growth/scripts/import-baseline.sh
sandbox/sdq-labs-growth/scripts/import-followup.sh
sandbox/sdq-labs-growth/scripts/import-validation.sh
sandbox/sdq-labs-growth/scripts/run-demo-flow.sh
sandbox/sdq-labs-growth/scripts/verify-demo.sh
sandbox/sdq-labs-growth/scripts/bootstrap-paperclip.sh
sandbox/sdq-labs-growth/scripts/verify-paperclip-flow.sh
```

Reset only sandbox tenant data:

```bash
sandbox/sdq-labs-growth/scripts/reset.sh
```
