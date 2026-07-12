# External Dependencies

| Dependency | Used For | Recovery Note |
|---|---|---|
| GitHub | code/config source of truth | clone repo; keep local archive for outages |
| Docker Desktop / Docker Engine | containers and Compose | install manually on macOS, Docker Engine on Ubuntu |
| Paperclip upstream | official control plane source | cloned by `platform/paperclip/scripts/clone-or-update.sh` |
| PyPI `hermes-agent` | Hermes CLI/runtime | installed into `.local/hermes/venv` |
| OpenAI / Anthropic | future live LLM calls | keys stored outside Git |
| Oracle Cloud | future production VM/runtime | production deployment not complete yet |
| Domain/DNS provider | future production URLs | keep registrar credentials in password manager |
| Homebrew | macOS packages | optional but recommended |
| Docker Hub / registries | base images | required during build/pull |
