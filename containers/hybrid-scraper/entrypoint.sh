#!/bin/sh

# If launched by the fleet conductor, symlink scrape.py from fleet-data
if [ -d "/fleet-data" ] && [ -n "$SCRAPER_ID" ]; then
    SHARED_SCRIPT="/fleet-data/$SCRAPER_ID/scraper.py"
    if [ -f "$SHARED_SCRIPT" ]; then
        echo "Fleet mode: linking scrape.py -> $SHARED_SCRIPT"
        ln -sf "$SHARED_SCRIPT" /app/scrape.py
    else
        echo "Fleet mode: WARNING — $SHARED_SCRIPT not found, using built-in scrape.py"
    fi
fi

# Start the browser server in the background
node /app/playwright-server/browser_server.js &
SERVER_PID=$!

# Remove stale config so we can detect when the server writes a fresh one
rm -f /app/playwright-server/config.json

# Wait for the server to write the ws_endpoint to config.json
echo "Waiting for browser server to start..."
while [ ! -f /app/playwright-server/config.json ] || ! grep -q "ws://" /app/playwright-server/config.json 2>/dev/null; do
    sleep 0.2
done

echo "Browser server ready: $(cat /app/playwright-server/config.json)"

# Export WS_ENDPOINT so scraper.py can read it from env
export WS_ENDPOINT=$(jq -r '.ws_endpoint' /app/playwright-server/config.json)

# Run the scraper, pipe JSON output through the ingestion layer
python3 /app/scrape.py | /app/ingest.sh

# Clean up
kill $SERVER_PID 2>/dev/null
