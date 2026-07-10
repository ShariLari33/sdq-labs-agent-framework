# SDQ Labs Agent Framework

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
