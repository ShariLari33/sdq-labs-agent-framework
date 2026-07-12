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

## Security Notes

- Do not place API keys in Paperclip instructions, `AGENTS.md`, or `SKILL.md`.
- Do not give Hermes direct database credentials.
- Keep scheduled autonomous heartbeats disabled during initial testing.
- Keep browser/web tools disabled until there is a reviewed need.
- Hermes should only read performance summaries through the SDQ API.
