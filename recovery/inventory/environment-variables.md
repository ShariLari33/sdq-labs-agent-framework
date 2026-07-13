# Environment Variables

| Variable | Service | Purpose | Secret | Required |
|---|---|---|---|---|
| `DATABASE_URL` | SDQ API | Connect API to SDQ PostgreSQL | yes | yes |
| `OPENAI_API_KEY` | SDQ/Paperclip/Hermes providers | Live OpenAI calls | yes | optional |
| `OPENAI_MODEL` | SDQ API | OpenAI model name | no | optional |
| `ANTHROPIC_API_KEY` | Paperclip/Hermes providers | Live Anthropic calls | yes | optional |
| `LLM_PROVIDER` | SDQ API | mock/openai selection | no | optional |
| `SDQ_INTERNAL_API_TOKEN` | SDQ/Paperclip/Hermes future integration | Internal service auth | yes | future |
| `PUBLIC_BASE_URL` | SDQ/reverse proxy | Public API URL | no | production |
| `PAPERCLIP_PUBLIC_URL` | Paperclip | Public/base URL | no | yes |
| `PAPERCLIP_DEPLOYMENT_MODE` | Paperclip | authenticated/local mode | no | yes |
| `PAPERCLIP_DEPLOYMENT_EXPOSURE` | Paperclip | private/public exposure | no | yes |
| `BETTER_AUTH_SECRET` | Paperclip | auth signing secret | yes | yes |
| `PAPERCLIP_POSTGRES_USER` | Paperclip DB | DB user | no | yes |
| `PAPERCLIP_POSTGRES_PASSWORD` | Paperclip DB | DB password | yes | yes |
| `PAPERCLIP_POSTGRES_DB` | Paperclip DB | DB name | no | yes |
| `DOMAIN_NAME` | reverse proxy | production hostname | no | future |
| `ACME_EMAIL` | reverse proxy | TLS registration email | no | future |
| `GOOGLE_API_KEY` | Hermes providers | optional Gemini/Google provider key | yes | optional |
| `OPENROUTER_API_KEY` | Hermes providers | optional OpenRouter provider key | yes | optional |
| `API_SERVER_KEY` | Hermes Gateway | bearer token for Hermes API server | yes | yes for gateway |
| `HERMES_GATEWAY_PORT` | Hermes Gateway | localhost port mapping | no | local |
| `HERMES_VERSION` | Hermes Gateway | installed hermes-agent package version | no | local/build |
| `PAPERCLIP_API_URL` | Hermes Gateway | Paperclip API URL reachable from gateway | no | optional |
