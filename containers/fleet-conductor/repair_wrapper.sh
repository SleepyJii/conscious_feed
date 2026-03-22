#!/bin/sh
# Repair wrapper — runs a dev-agent repair (blocking), then cleans up
# the debug container and records the outcome in scraper_runs.
#
# Usage: repair_wrapper.sh <compose_file> <scraper_id> <repair_service_name> <debug_container_id> [repair_timeout]

set -u

COMPOSE_FILE="$1"
SCRAPER_ID="$2"
REPAIR_SERVICE="$3"
DEBUG_CONTAINER="$4"
REPAIR_TIMEOUT="${5:-${REPAIR_TIMEOUT:-900}}"
EVENTS_URL="http://restful_db:5000/register_event"

cleanup() {
    docker rm -f "$DEBUG_CONTAINER" 2>/dev/null
    for NAME_FILTER in "fleet-${SCRAPER_ID}-run" "fleet-${REPAIR_SERVICE}-run"; do
        docker ps -q --filter "name=$NAME_FILTER" 2>/dev/null | while read -r CID; do
            [ -n "$CID" ] && docker rm -f "$CID" 2>/dev/null
        done
    done
    curl -sf -X POST "http://localhost:8000/scrapers/${SCRAPER_ID}/stop" >/dev/null 2>&1 || true
}
trap cleanup EXIT

emit_event() {
    curl -s -X POST "$EVENTS_URL" \
        -H "Content-Type: application/json" \
        -d "$1" >/dev/null 2>&1 || true
}

# Run repair agent (blocking — waits for it to finish)
timeout "$REPAIR_TIMEOUT" docker compose -p fleet -f "$COMPOSE_FILE" run --rm "$REPAIR_SERVICE"
REPAIR_EXIT=$?

if [ "$REPAIR_EXIT" -eq 124 ]; then
    echo "repair_wrapper: repair agent for $SCRAPER_ID timed out after ${REPAIR_TIMEOUT}s" >&2
fi

# Record outcome in scraper_runs so consecutive_failures updates:
# - Success (exit 0): resets consecutive_failures, policy goes back to RETRY
# - Failure (exit != 0): advances consecutive_failures, policy moves forward
NOW=$(date -u +"%Y-%m-%d %H:%M:%S+00")
export PGPASSWORD="${DB_PASS:-conscious_feed}"
if [ "$REPAIR_EXIT" -eq 0 ]; then
    psql -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-conscious_feed}" -d "${DB_NAME:-scrape_db}" -q <<SQL
INSERT INTO scraper_runs (scraper_id, started_at, finished_at, exit_code, stderr_tail, rows_inserted)
VALUES ('${SCRAPER_ID}', '${NOW}', '${NOW}', 0, 'repair agent succeeded', 0);
SQL
else
    psql -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-conscious_feed}" -d "${DB_NAME:-scrape_db}" -q <<SQL
INSERT INTO scraper_runs (scraper_id, started_at, finished_at, exit_code, stderr_tail, rows_inserted)
VALUES ('${SCRAPER_ID}', '${NOW}', '${NOW}', 1, 'repair agent failed (exit ${REPAIR_EXIT})', 0);
SQL
fi

emit_event "{\"source\":\"conductor\",\"event_type\":\"repair_cleanup\",\"container_id\":\"${SCRAPER_ID}\",\"event_payload\":{\"repair_exit_code\":${REPAIR_EXIT}}}"

# Container cleanup and /stop call handled by EXIT trap
