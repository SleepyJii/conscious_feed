#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

docker compose down
docker compose -p fleet down
"$SCRIPT_DIR/build.sh"
docker compose up -d
