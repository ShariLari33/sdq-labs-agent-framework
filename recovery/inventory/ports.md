# Ports Inventory

| Port | Service | Local Binding | Production Exposure |
|---|---|---|---|
| 5432 | SDQ PostgreSQL | `0.0.0.0:5432->5432` | do not expose publicly |
| 8000 | SDQ API | `0.0.0.0:8000->8000` | behind reverse proxy or private network |
| 8080 | Adminer | `0.0.0.0:8080->8080` | local only; do not expose |
| 3100 | Paperclip | `0.0.0.0:3100->3100` | behind reverse proxy/TLS |
| 8642 | Hermes Gateway | `127.0.0.1:8642->8642` | private network only, behind HTTPS if remote |
| 5432 internal | Paperclip PostgreSQL | container-only `5432/tcp` | do not expose publicly |
| 80/443 | reverse proxy | future | public HTTPS only |
