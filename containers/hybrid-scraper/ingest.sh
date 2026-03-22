#!/bin/sh
# ingest.sh — reads JSONL from stdin, enriches, and upserts into PostgreSQL.
# Non-JSON lines are forwarded to stderr as log output.
# Dedup: rows with matching (page_url, title, published_at) are updated, not duplicated.

set -eu

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-conscious_feed}"
DB_USER="${DB_USER:-conscious_feed}"
DB_PASS="${DB_PASS:-conscious_feed}"
EVENTS_URL="http://restful_db:5000/register_event"

export PGPASSWORD="$DB_PASS"

ROWS_OK=0
ROWS_FAILED=0

while IFS= read -r line; do
    # Try to parse as JSON — skip non-JSON lines
    if ! echo "$line" | jq -e . >/dev/null 2>&1; then
        echo "[scraper-log] $line" >&2
        continue
    fi

    # Enrich with metadata from environment
    enriched=$(echo "$line" | jq -c \
        --arg sid "${SCRAPER_ID:-unknown}" \
        --arg sname "${SCRAPER_NAME:-}" \
        --arg turl "${TARGET_URL:-}" \
        --arg scat "${SCRAPER_CATEGORY:-}" \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '. + {scraper_id: $sid, scraper_name: $sname, target_url: $turl, category: $scat, scraped_at: $ts}')

    # Extract fields for SQL
    s_id=$(echo "$enriched" | jq -r '.scraper_id')
    s_name=$(echo "$enriched" | jq -r '.scraper_name')
    s_cat=$(echo "$enriched" | jq -r '.category // ""')
    t_url=$(echo "$enriched" | jq -r '.target_url')
    page_url=$(echo "$enriched" | jq -r '.url // .target_url')
    title=$(echo "$enriched" | jq -r '.title // ""')
    content=$(echo "$enriched" | jq -r '.content // ""')
    published_at=$(echo "$enriched" | jq -r '.published_at // empty')
    scraped_at=$(echo "$enriched" | jq -r '.scraped_at')
    raw_json="$enriched"

    # Build published_at SQL value (NULL if not provided)
    if [ -n "$published_at" ]; then
        pub_sql="'$(echo "$published_at" | sed "s/'/''/g")'::timestamptz"
    else
        pub_sql="NULL"
    fi

    # Upsert: insert or update on (page_url, title, published_at) conflict
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q -c \
        "INSERT INTO scrape_results (scraper_id, scraper_name, category, target_url, page_url, title, content, published_at, raw_json, scraped_at)
         VALUES (
            '$(echo "$s_id" | sed "s/'/''/g")',
            '$(echo "$s_name" | sed "s/'/''/g")',
            '$(echo "$s_cat" | sed "s/'/''/g")',
            '$(echo "$t_url" | sed "s/'/''/g")',
            '$(echo "$page_url" | sed "s/'/''/g")',
            '$(echo "$title" | sed "s/'/''/g")',
            '$(echo "$content" | sed "s/'/''/g")',
            $pub_sql,
            '$(echo "$raw_json" | sed "s/'/''/g")'::jsonb,
            '$scraped_at'::timestamptz
         )
         ON CONFLICT (page_url, title, (COALESCE(published_at, '1970-01-01'::timestamptz)))
         DO UPDATE SET
            content = EXCLUDED.content,
            raw_json = EXCLUDED.raw_json,
            scraped_at = EXCLUDED.scraped_at;" 2>&1; then
        ROWS_OK=$((ROWS_OK + 1))
        # Echo ingested line to stdout so callers can count rows
        echo "$line"
    else
        ROWS_FAILED=$((ROWS_FAILED + 1))
        echo "[ingest] ERROR inserting row" >&2
    fi
done

# Emit ingest summary event
curl -s -X POST "$EVENTS_URL" \
    -H "Content-Type: application/json" \
    -d "{\"source\":\"hybrid-scraper\",\"event_type\":\"ingest_completed\",\"container_id\":\"${SCRAPER_ID:-unknown}\",\"event_payload\":{\"rows_inserted\":${ROWS_OK},\"rows_failed\":${ROWS_FAILED}}}" \
    >/dev/null 2>&1 || true

echo "[ingest] Done. inserted=${ROWS_OK} failed=${ROWS_FAILED}" >&2
