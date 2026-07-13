# SDQ Sandbox

This directory contains synthetic demo environments for the SDQ Labs Agent Framework.

## One-Command Demo

Run:

```bash
make sandbox
```

The command starts Docker, bootstraps the `SDQ Labs Growth Sandbox` tenant, imports synthetic Google Ads datasets, creates baseline/follow-up/validation tasks, runs the task engine, approves demo approvals as `Sharif`, creates performance feedback, approves a learning candidate, creates and approves an evolution proposal, verifies the newest skill version, and prints `SANDBOX READY`.

All data is fictional. Do not use real Google Ads credentials or live customer data.

## Manual Commands

```bash
sandbox/sdq-labs-growth/scripts/bootstrap.sh
sandbox/sdq-labs-growth/scripts/import-baseline.sh
sandbox/sdq-labs-growth/scripts/import-followup.sh
sandbox/sdq-labs-growth/scripts/import-validation.sh
sandbox/sdq-labs-growth/scripts/run-demo-flow.sh
sandbox/sdq-labs-growth/scripts/verify-demo.sh
```

Reset only sandbox tenant data:

```bash
sandbox/sdq-labs-growth/scripts/reset.sh
```

