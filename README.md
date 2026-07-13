# SDQ Labs Agent Framework

## Recovery Philosophy

Git is the source of truth for code, configuration templates, scripts, agent instructions, and skills. Git is not the source of truth for secrets, database contents, Docker volumes, or runtime state.

For a fresh local setup:

```bash
git clone https://github.com/ShariLari33/sdq-labs-agent-framework.git
cd sdq-labs-agent-framework
cp .env.example .env
make bootstrap-local
make verify-local
```

See `recovery/README.md` for full recovery, backup, and disaster procedures. Oracle Cloud will become the device-independent runtime after production deployment is implemented.

## Control plane

This repo can run the official Paperclip control plane locally next to the SDQ API. Paperclip is kept separate from SDQ internals: its source is cloned into `.local/platform/paperclip-source`, its secrets live in `platform/paperclip/.env`, and it runs with its own Postgres database.

Start it after the SDQ API stack is running:

```bash
make paperclip-start
```

Then open `http://localhost:3100` and create the first admin account. See `platform/paperclip/README.md` for details, verification, logs, and stop commands.

## Docker acceptance checks

Start the stack:

```bash
docker compose up -d --build
```

Check provider health without making a paid model call:

```bash
curl -s http://localhost:8000/llm-providers/health
```

Run the default mock execution path:

```bash
curl -s -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"demo-partner-a","title":"LLM provider smoke test","input":{"channel":"google_ads","period":"last_30_days"}}'

curl -s -X POST http://localhost:8000/task-engine/run-next/demo-partner-a
curl -s http://localhost:8000/agent-runs/demo-partner-a
curl -s http://localhost:8000/events/demo-partner-a
```

To test OpenAI execution, set `OPENAI_API_KEY`, set `OPENAI_MODEL`, update a model route through the development endpoint, then run the same task flow. Do not put API keys in task payloads.

## Synthetic Growth Sandbox

The repo includes a complete fictional sandbox company at `sandbox/sdq-labs-growth/` for end-to-end testing before a real company or live advertising account exists.

Warning: all sandbox company details and Google Ads rows are synthetic. Never use real ad credentials with these scripts.

Start the local stack:

```bash
docker compose up -d --build
```

Bootstrap the sandbox tenant and import baseline data:

```bash
sandbox/sdq-labs-growth/scripts/load-baseline.sh
```

Run the full repeatable demo flow:

```bash
sandbox/sdq-labs-growth/scripts/run-demo-flow.sh
```

Verify the current demo state:

```bash
sandbox/sdq-labs-growth/scripts/verify-demo-flow.sh
```

Reset only the sandbox tenant's imported data, tasks, runs, approvals, memory, learnings, improvement candidates, events, and feedback:

```bash
sandbox/sdq-labs-growth/scripts/reset-sandbox-data.sh
```

The demo uses tenant slug `sdq-labs-growth-sandbox` and synthetic Google Ads periods for baseline, follow-up, and validation analysis.
