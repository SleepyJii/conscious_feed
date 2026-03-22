#!/bin/sh
# Cron wrapper — runs a scraper via docker compose and records the outcome
# in the scraper_runs table, and emits events to db-restful.
#
# Usage: run_wrapper.sh <compose_file> <scraper_id>

set -u

COMPOSE_FILE="$1"
SCRAPER_ID="$2"
EVENTS_URL="http://restful_db:5000/register_event"

emit_event() {
    curl -s -X POST "$EVENTS_URL" \
        -H "Content-Type: application/json" \
        -d "$1" >/dev/null 2>&1 || true
}

# Check current policy action — only run on RETRY
POLICY_ACTION=$(curl -sf "http://localhost:8000/scrapers/${SCRAPER_ID}" | jq -r '.current_policy_action // "RETRY"' 2>/dev/null)
if [ "$POLICY_ACTION" != "RETRY" ]; then
    emit_event "{\"source\":\"conductor\",\"event_type\":\"scraper_skipped\",\"container_id\":\"${SCRAPER_ID}\",\"event_payload\":{\"reason\":\"policy_action_${POLICY_ACTION}\"}}"
    exit 0
fi

STARTED_AT=$(date -u +"%Y-%m-%d %H:%M:%S+00")

emit_event "{\"source\":\"conductor\",\"event_type\":\"scraper_launched\",\"container_id\":\"${SCRAPER_ID}\",\"event_payload\":{\"trigger\":\"cron\"}}"

STDOUT_FILE=$(mktemp)
STDERR_FILE=$(mktemp)
docker compose -p fleet -f "$COMPOSE_FILE" run --rm "$SCRAPER_ID" >"$STDOUT_FILE" 2>"$STDERR_FILE"
EXIT_CODE=$?

FINISHED_AT=$(date -u +"%Y-%m-%d %H:%M:%S+00")
ROWS_INSERTED=$(grep -c . "$STDOUT_FILE" 2>/dev/null || echo 0)
STDERR_TAIL=$(tail -c 2000 "$STDERR_FILE")
rm -f "$STDOUT_FILE" "$STDERR_FILE"

emit_event "{\"source\":\"conductor\",\"event_type\":\"scraper_run_completed\",\"container_id\":\"${SCRAPER_ID}\",\"event_payload\":{\"trigger\":\"cron\",\"exit_code\":${EXIT_CODE},\"rows_inserted\":${ROWS_INSERTED}}}"

export PGPASSWORD="${DB_PASS:-conscious_feed}"
psql -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-conscious_feed}" -d "${DB_NAME:-scrape_db}" -q <<SQL
INSERT INTO scraper_runs (scraper_id, started_at, finished_at, exit_code, stderr_tail, rows_inserted)
VALUES ('${SCRAPER_ID}', '${STARTED_AT}', '${FINISHED_AT}', ${EXIT_CODE}, '$(echo "$STDERR_TAIL" | sed "s/'/''/g")', ${ROWS_INSERTED});
SQL
