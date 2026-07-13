# New Device Setup

Use this for a clean macOS development machine.

## Install Prerequisites

1. Install Apple command line tools:

```bash
xcode-select --install
```

2. Install Homebrew if absent:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Install Git and Python 3.11+ if needed:

```bash
brew install git python@3.11
```

4. Install Docker Desktop manually from Docker, start it, and wait until Docker is running.

## Clone And Bootstrap

```bash
git clone https://github.com/ShariLari33/sdq-labs-agent-framework.git
cd sdq-labs-agent-framework
cp .env.example .env
make bootstrap-local
make verify-local
make hermes-gateway-start
make hermes-gateway-verify
```

`make bootstrap-local` is safe to rerun. It starts SDQ services, starts Paperclip through the existing Paperclip scripts, and installs Hermes into `.local/hermes/venv`.

## Manual Steps Still Required

- Open `http://localhost:3100`.
- Create or log into the Paperclip admin account.
- Configure the Hermes agent manually where Paperclip API automation is unavailable.
- Prefer adapter `hermes_gateway` for Dockerized Paperclip.
- Use API base URL: `http://hermes-gateway:8642`.
- Use API key from `runtime/hermes/gateway/.env`.
- Store provider/API credentials in a password manager, not in Git.

## Do Not Commit

- `.env`
- `platform/paperclip/.env`
- `.local/`
- backups or database dumps
- provider keys or SSH private keys
