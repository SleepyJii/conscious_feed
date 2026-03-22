#!/bin/sh
# Tears down all containers, removes Docker volumes and local data
# for a completely fresh start. Run from anywhere in the repo.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

. "$SCRIPT_DIR/load_config.sh" 2>/dev/null || true

echo "Stopping and removing all containers..."
docker compose down --remove-orphans

echo "Clearing local volume data (via Docker for permissions)..."
docker run --rm -v "${PWD}/volumes:/volumes" alpine sh -c "rm -rf /volumes/fleet-data/* /volumes/postgres_data/*"
echo "  cleared volumes/fleet-data and volumes/postgres_data"

echo "Removing named Docker volumes..."
docker volume rm fleet-data 2>/dev/null && echo "  removed fleet-data" || echo "  fleet-data not found (skipping)"
docker volume rm postgres-data 2>/dev/null && echo "  removed postgres-data" || echo "  postgres-data not found (skipping)"

# Legacy volumes from before refactors
docker volume rm conductor-fleet 2>/dev/null && echo "  removed conductor-fleet" || echo "  conductor-fleet not found (skipping)"
docker volume rm fleet-shared 2>/dev/null && echo "  removed fleet-shared" || echo "  fleet-shared not found (skipping)"
docker volume rm conscious_feed_pgdata 2>/dev/null && echo "  removed conscious_feed_pgdata" || echo "  conscious_feed_pgdata not found (skipping)"

echo "Ensuring volume mount directories exist..."
mkdir -p volumes/fleet-data volumes/postgres_data

echo "Done. Run ./scripts/build.sh && ./scripts/launch.sh to start fresh."
