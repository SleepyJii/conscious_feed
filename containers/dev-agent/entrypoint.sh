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
    echo "dev-agent: MCP server mode on port 8080"
    exec python3 /app/mcp_server.py
fi

# Start MCP server in background so repair.py can use its tools
python3 /app/mcp_server.py &
MCP_PID=$!

# Wait for MCP server to be ready
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/mcp -o /dev/null 2>/dev/null; then
        break
    fi
    sleep 0.5
done

# Run the repair agent
python3 /app/repair.py
EXIT_CODE=$?

kill $MCP_PID 2>/dev/null || true

emit_event "{\"source\":\"dev-agent\",\"event_type\":\"repair_completed\",\"container_id\":\"${SCRAPER_ID}\",\"event_payload\":{\"exit_code\":${EXIT_CODE}}}"

exit $EXIT_CODE
