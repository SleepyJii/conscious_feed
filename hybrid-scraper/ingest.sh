#!/bin/sh
# ingest.sh — reads JSONL from stdin, enriches, and inserts into PostgreSQL.
# Non-JSON lines are forwarded to stderr as log output.

set -eu

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-conscious_feed}"
DB_USER="${DB_USER:-conscious_feed}"
DB_PASS="${DB_PASS:-conscious_feed}"

export PGPASSWORD="$DB_PASS"

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
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '. + {scraper_id: $sid, scraper_name: $sname, target_url: $turl, scraped_at: $ts}')

    # Extract fields for SQL
    s_id=$(echo "$enriched" | jq -r '.scraper_id')
    s_name=$(echo "$enriched" | jq -r '.scraper_name')
    t_url=$(echo "$enriched" | jq -r '.target_url')
    page_url=$(echo "$enriched" | jq -r '.url // .target_url')
    title=$(echo "$enriched" | jq -r '.title // ""')
    content=$(echo "$enriched" | jq -r '.content // ""')
    scraped_at=$(echo "$enriched" | jq -r '.scraped_at')
    raw_json="$enriched"

    # Insert into PostgreSQL (escape single quotes for SQL)
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q -c \
        "INSERT INTO scrape_results (scraper_id, scraper_name, target_url, page_url, title, content, raw_json, scraped_at)
         VALUES (
            '$(echo "$s_id" | sed "s/'/''/g")',
            '$(echo "$s_name" | sed "s/'/''/g")',
            '$(echo "$t_url" | sed "s/'/''/g")',
            '$(echo "$page_url" | sed "s/'/''/g")',
            '$(echo "$title" | sed "s/'/''/g")',
            '$(echo "$content" | sed "s/'/''/g")',
            '$(echo "$raw_json" | sed "s/'/''/g")'::jsonb,
            '$scraped_at'::timestamptz
         );" 2>&1 || echo "[ingest] ERROR inserting row" >&2
done

echo "[ingest] Done." >&2
