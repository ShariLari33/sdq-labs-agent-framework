# Paperclip Hermes Setup

Paperclip supports local Hermes execution with the `hermes_local` adapter. The local Hermes CLI must be installed and authenticated/configured on the host before running real agent work.

## Manual Browser Steps

1. Open `http://localhost:3100`.
2. Create a company:
   - Name: `SDQ Labs MVP`
   - Purpose: `Validate autonomous Google Ads performance optimisation`
3. Create an agent:
   - Name: `Google Ads Performance Analyst`
   - Role: `performance analyst`
   - Adapter: `hermes_local`
   - Working directory: `/Users/sharifsediqui/Developer/sdq-labs-agent-framework/runtime/hermes/google-ads-agent/workspace`
   - Persist session: enabled
   - Timeout: `300` seconds
   - Toolsets initially: `terminal,file`
   - Browser/web: disabled initially
   - Wake on assignment: enabled
   - Scheduled heartbeat: disabled for the first test
4. Add instructions using the managed instructions bundle or prompt template.
5. Reference `runtime/hermes/google-ads-agent/AGENTS.md` and the approved Google Ads Performance Analysis skill.
6. Run Test Environment before saving.
7. Create one task for `demo-partner-a`.
8. Require approval before any external action.

## Recommended: Hermes Gateway Adapter

Paperclip is running inside Docker. Do not use a macOS host path as the Paperclip command for this containerized setup. Use Hermes Gateway instead.

Start the gateway:

```bash
make hermes-gateway-start
make hermes-gateway-verify
```

Discovered Paperclip adapter:

- Adapter type: `hermes_gateway`
- Gateway health endpoint: `GET /health`
- Authentication: `Authorization: Bearer <API_SERVER_KEY>`
- Paperclip calls Hermes with:
  - `POST /v1/runs`
  - `GET /v1/runs/{run_id}/events`
  - `GET /v1/runs/{run_id}`
  - `POST /v1/runs/{run_id}/stop`

## Update Existing Google Ads Performance Analyst

For the local MVP, edit the existing `Google Ads Performance Analyst` agent and switch it to the gateway adapter where the UI allows it.

Use these adapter fields:

- Adapter: `hermes_gateway`
- API base URL: `http://hermes-gateway:8642`
- API key: the value of `API_SERVER_KEY` from `runtime/hermes/gateway/.env`
- Paperclip API URL: `http://server:3100/api`
- Session key strategy: `issue`
- Timeout seconds: `1800`
- Event reconnect ms: `2000`
- Instructions: reference `AGENTS.md` and the Google Ads Performance Analysis skill
- Model: `Default`
- Provider: `Auto`
- Thinking effort: `Auto`
- Max turns: `20`
- Persist session: enabled
- Worktree mode: disabled
- Checkpoints: disabled initially
- Quiet output: enabled
- Verbose output: disabled
- Scheduled heartbeat: disabled
- Toolsets initially: `terminal,file`
- Browser/web: disabled initially
- Working directory/workspace: managed by the Hermes Gateway container at `/home/hermes/workspace`

Hermes Gateway receives environment variables from `runtime/hermes/gateway/.env` and Compose:

```text
SDQ_API_BASE_URL=http://api:8000
PAPERCLIP_API_URL=http://server:3100/api
```

Do not add provider keys until you intentionally want live model calls.

Click `Test Agent`.

Expected success criteria:

- Paperclip no longer reports `Hermes CLI "hermes" not found in PATH`.
- Paperclip can reach `http://hermes-gateway:8642/health`.
- Test Agent succeeds without a paid model request where Paperclip only probes the environment.
- The gateway can reach SDQ at `http://api:8000`.
- The gateway sees `/home/hermes/workspace`, `/home/hermes/AGENTS.md`, `/home/hermes/skills`, and `/home/hermes/scripts`.

## Invite External Agent Flow

Paperclip source includes an agent-only invite/onboarding flow for gateway agents. The smoke helper verifies that invite onboarding text contains:

- `adapterType: "hermes_gateway"`
- `API_SERVER_ENABLED=true`
- `API_SERVER_KEY`
- `hermes gateway run --replace --accept-hooks`
- `agentDefaultsPayload.apiBaseUrl`

Use Invite External Agent when you want Hermes Gateway to register as a new remote runtime through Paperclip's join request workflow. Use direct edit when you are updating the already-created local MVP agent.

## Security Notes

- Do not place API keys in Paperclip instructions, `AGENTS.md`, or `SKILL.md`.
- Do not give Hermes direct database credentials.
- Keep scheduled autonomous heartbeats disabled during initial testing.
- Keep browser/web tools disabled until there is a reviewed need.
- Hermes should only read performance summaries through the SDQ API.
