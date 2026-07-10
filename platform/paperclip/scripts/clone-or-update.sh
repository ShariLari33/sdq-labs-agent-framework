#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SOURCE_DIR="$REPO_ROOT/.local/platform/paperclip-source"
UPSTREAM_URL="https://github.com/paperclipai/paperclip.git"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to clone Paperclip, but it was not found on PATH." >&2
  exit 1
fi

mkdir -p "$(dirname "$SOURCE_DIR")"

if [ -d "$SOURCE_DIR/.git" ]; then
  echo "Updating official Paperclip source in $SOURCE_DIR"
  git -C "$SOURCE_DIR" fetch origin
else
  echo "Cloning official Paperclip source into $SOURCE_DIR"
  git clone "$UPSTREAM_URL" "$SOURCE_DIR"
fi

branch="$(git -C "$SOURCE_DIR" branch --show-current || true)"
commit="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"

echo "Paperclip source: $SOURCE_DIR"
echo "Paperclip branch: ${branch:-detached}"
echo "Paperclip commit: $commit"
