#!/bin/sh

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

# Run the Python client
python3 /app/scrape.py

# Clean up
kill $SERVER_PID 2>/dev/null
