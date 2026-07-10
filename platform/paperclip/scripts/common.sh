#!/usr/bin/env bash

paperclip_repo_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir/../../.." && pwd
}

paperclip_compose_file() {
  local source_dir="$1"
  local candidate

  for candidate in \
    "$source_dir/docker/docker-compose.yml" \
    "$source_dir/docker/docker-compose.yaml" \
    "$source_dir/docker/compose.yml" \
    "$source_dir/docker/compose.yaml" \
    "$source_dir/docker-compose.yml" \
    "$source_dir/docker-compose.yaml" \
    "$source_dir/compose.yml" \
    "$source_dir/compose.yaml"
  do
    if [ -f "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "Could not find an official Paperclip Docker Compose file under $source_dir." >&2
  echo "Found candidates:" >&2
  find "$source_dir" -maxdepth 4 \( -iname '*compose*.yml' -o -iname '*compose*.yaml' \) -print >&2 || true
  return 1
}

paperclip_env_load() {
  local env_file="$1"

  if [ ! -f "$env_file" ]; then
    echo "Missing $env_file. Run platform/paperclip/scripts/start.sh first." >&2
    return 1
  fi

  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
}

paperclip_compose() {
  local repo_root="$1"
  local compose_file="$2"
  local env_file="$3"
  shift 3

  docker compose \
    --env-file "$env_file" \
    -f "$compose_file" \
    -f "$repo_root/platform/paperclip/docker-compose.override.yml" \
    -p sdq-paperclip \
    "$@"
}

paperclip_wait_for_health() {
  local url="${1:-http://localhost:3100/api/health}"
  local attempts="${2:-60}"
  local i

  for i in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Paperclip did not become healthy at $url." >&2
  return 1
}
