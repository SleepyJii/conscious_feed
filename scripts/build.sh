#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."

docker compose -f "$PROJECT_ROOT/docker-compose.yml" --profile build-only build "$@"
