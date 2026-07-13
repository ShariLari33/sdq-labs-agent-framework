#!/usr/bin/env bash

gateway_repo_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir/../../../.." && pwd
}

gateway_dir() {
  local repo_root="$1"
  printf '%s\n' "$repo_root/runtime/hermes/gateway"
}

gateway_env_file() {
  local repo_root="$1"
  printf '%s\n' "$(gateway_dir "$repo_root")/.env"
}

gateway_compose() {
  local repo_root="$1"
  shift
  docker compose \
    --env-file "$(gateway_env_file "$repo_root")" \
    -f "$(gateway_dir "$repo_root")/docker-compose.yml" \
    -p sdq-hermes-gateway \
    "$@"
}

gateway_require_env() {
  local env_file="$1"
  if [ ! -f "$env_file" ]; then
    echo "Missing $env_file. Run: make hermes-gateway-start" >&2
    return 1
  fi
  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
  : "${API_SERVER_KEY:?API_SERVER_KEY is required}"
  : "${HERMES_GATEWAY_PORT:=8642}"
}

gateway_prepare_env() {
  local repo_root="$1"
  local dir env_file example key tmp_file
  dir="$(gateway_dir "$repo_root")"
  env_file="$dir/.env"
  example="$dir/.env.example"

  if [ -f "$env_file" ]; then
    return 0
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl is required to generate local API_SERVER_KEY." >&2
    return 1
  fi

  cp "$example" "$env_file"
  key="$(openssl rand -hex 32)"
  tmp_file="$(mktemp)"
  sed -e "s/^API_SERVER_KEY=.*/API_SERVER_KEY=$key/" "$env_file" > "$tmp_file"
  mv "$tmp_file" "$env_file"
  chmod 600 "$env_file"
  echo "Created $env_file with a generated local API_SERVER_KEY. The value was not printed."
}
