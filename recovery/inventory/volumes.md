# Volumes Inventory

| Volume | Service | Content | Backup Required | Sensitivity |
|---|---|---|---|---|
| `sdq-labs-agent-framework_sdq_postgres_data` | SDQ PostgreSQL | SDQ app data, tenants, tasks, skills, memory, performance data | yes | high |
| `sdq-paperclip_pgdata` | Paperclip PostgreSQL | Paperclip companies, agents, tasks, auth/app state | yes | high |
| `sdq-paperclip_paperclip-data` | Paperclip server | Paperclip app files/workspace data | yes | high |
| `.local/hermes/venv` | Hermes | reproducible local virtualenv | no | low |
| `.local/hermes/state` | Hermes | repository-local Hermes runtime state | review/encrypt if needed | high |
| `.local/hermes/config` | Hermes | repository-local Hermes config | review/encrypt if needed | high |
| `sdq-hermes-gateway_sdq_hermes_gateway_state` | Hermes Gateway | Dockerized Hermes runtime state | yes after review/encryption | high |
| `.local/platform/paperclip-source` | Paperclip source clone | official upstream clone | no | low |
| `runtime/hermes/google-ads-agent/workspace` | Hermes agent workspace | isolated agent work files | review before backup | medium |
