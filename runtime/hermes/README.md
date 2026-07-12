# Hermes Local Runtime

This directory prepares a local, isolated Hermes workspace for Paperclip's `hermes_local` adapter. Paperclip remains the control plane, SDQ remains the tenant-scoped data/tool layer, and Hermes runs from a narrow working directory instead of the full repository.

Hermes working directory:

```text
runtime/hermes/google-ads-agent/workspace
```

Use the absolute path to that directory when configuring the Paperclip agent.

## MVP Tool Direction

For the MVP, Hermes may call approved SDQ HTTP endpoints through controlled scripts in `runtime/hermes/google-ads-agent/scripts`.

The initial tool boundary is:

- read deterministic SDQ summaries through the SDQ API
- no direct database credentials
- no direct Google Ads writes
- no broad browser/web tools
- external changes require Paperclip approval

## Later

Later, SDQ tools can be exposed as MCP tools with tighter contracts:

- require `tenant_slug`
- require an internal service token
- allow only specific read endpoints
- keep write actions behind Paperclip approval

## Local Install

```bash
make hermes-install
```

This creates `.local/hermes/venv` and installs `hermes-agent`. It does not configure provider API keys and does not overwrite existing Hermes config.

## Verify

```bash
make hermes-verify
make hermes-test-sdq TENANT=demo-partner-a
```

No paid model calls are made by these checks.
