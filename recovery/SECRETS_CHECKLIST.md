# Secrets Checklist

Never commit:

- `.env`
- `platform/paperclip/.env`
- `.env.production`
- SSH private keys
- provider API keys
- database dumps
- Paperclip database backups
- Oracle credentials

Store in a password manager:

- GitHub tokens
- Oracle Cloud credentials
- SDQ production database password
- Paperclip production database password
- `BETTER_AUTH_SECRET`
- `SDQ_INTERNAL_API_TOKEN`
- OpenAI/Anthropic/provider keys
- DNS/registrar credentials

Generate local development secrets with `openssl rand -hex 32` when scripts do not generate them.

Rotate immediately after:

- laptop loss
- server compromise
- accidental commit
- suspicious Paperclip/GitHub/provider activity

Run:

```bash
make verify-local
git ls-files | grep -E '(^|/)\.env$|\.pem$|\.key$|\.dump$|\.sql'
```
