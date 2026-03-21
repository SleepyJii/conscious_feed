#!/bin/sh
# Dev-agent entrypoint — runs the repair script and emits a completion event.
#
# In sockpuppet mode (SOCKPUPPET=1), skips repair.py and just sleeps,
# allowing an external agent to exec in.

set -u

EVENTS_URL="http://restful_db:5000/register_event"
SCRAPER_ID="${SCRAPER_ID:-unknown}"

emit_event() {
    curl -s -X POST "$EVENTS_URL" \
        -H "Content-Type: application/json" \
        -d "$1" >/dev/null 2>&1 || true
}

if [ "${SOCKPUPPET:-}" = "1" ]; then
    echo "dev-agent: sockpuppet mode, waiting for external agent"
    exec sleep infinity
fi

# Run the repair script
python3 /app/repair.py
EXIT_CODE=$?

emit_event "{\"source\":\"dev-agent\",\"event_type\":\"repair_completed\",\"container_id\":\"${SCRAPER_ID}\",\"event_payload\":{\"exit_code\":${EXIT_CODE}}}"

exit $EXIT_CODE
