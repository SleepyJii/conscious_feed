#!/bin/sh
# Cron-triggered script: finds scrapers whose repair_policy step is REPAIR:<model>
# and triggers the repair endpoint for each, up to the concurrency limit.

set -u

API_URL="http://localhost:8000"
MAX_CONCURRENT="${MAX_CONCURRENT_REPAIRS:-2}"

# Count currently running repair containers
RUNNING=$(docker ps --filter "name=repair-" -q 2>/dev/null | wc -l)

# Get candidates from the conductor API (now returns objects with scraper_id + model)
CANDIDATES_JSON=$(curl -sf "$API_URL/scrapers/repair-candidates" | jq -c '.candidates[]' 2>/dev/null)

if [ -z "$CANDIDATES_JSON" ]; then
    exit 0
fi

echo "$CANDIDATES_JSON" | while read -r CANDIDATE; do
    if [ "$RUNNING" -ge "$MAX_CONCURRENT" ]; then
        echo "launch-repairs: max concurrent ($MAX_CONCURRENT) reached, stopping"
        break
    fi

    SCRAPER_ID=$(echo "$CANDIDATE" | jq -r '.scraper_id')
    MODEL=$(echo "$CANDIDATE" | jq -r '.model')

    # Skip if a repair container is already running for this scraper
    if docker ps -q --filter "name=repair-$SCRAPER_ID" 2>/dev/null | grep -q .; then
        echo "launch-repairs: repair already running for $SCRAPER_ID, skipping"
        continue
    fi

    echo "launch-repairs: triggering repair for $SCRAPER_ID with model $MODEL"
    curl -sf -X POST "$API_URL/scrapers/$SCRAPER_ID/repair" \
        -H "Content-Type: application/json" \
        -d "{\"lazy\": true, \"model\": \"$MODEL\"}" >/dev/null || true
    RUNNING=$((RUNNING + 1))
done
