#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# TODO: launch all services together once UI is integrated
docker compose up conductor db db-restful "$@"
