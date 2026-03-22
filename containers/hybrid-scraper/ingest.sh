#!/bin/sh
# ingest.sh — reads JSONL from stdin, enriches, and upserts into PostgreSQL.
# Non-JSON lines are forwarded to stderr as log output.
# Dedup: rows with matching (page_url, title, published_at) are updated, not duplicated.
#
# Uses a JSON-in-SQL approach: the entire enriched JSON is inserted as a jsonb
# literal and fields are extracted in SQL, avoiding all shell escaping issues.

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
    if ! printf '%s\n' "$line" | jq -e . >/dev/null 2>&1; then
        echo "[scraper-log] $line" >&2
        continue
    fi

    # Enrich with metadata from environment (output is a single-line JSON string)
    enriched=$(printf '%s\n' "$line" | jq -c \
        --arg sid "${SCRAPER_ID:-unknown}" \
        --arg sname "${SCRAPER_NAME:-}" \
        --arg turl "${TARGET_URL:-}" \
        --arg scat "${SCRAPER_CATEGORY:-}" \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '. + {scraper_id: $sid, scraper_name: $sname, target_url: $turl, category: $scat, scraped_at: $ts}')

    # Escape single quotes for SQL jsonb literal (the enriched JSON is always one line from jq -c)
    escaped=$(printf '%s' "$enriched" | sed "s/'/''/g")

    # Insert using jsonb field extraction — all text fields are extracted in SQL,
    # so we never pass content through shell interpolation.
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q -c \
        "WITH src AS (SELECT '${escaped}'::jsonb AS d)
         INSERT INTO scrape_results (scraper_id, scraper_name, category, target_url, page_url, title, content, published_at, raw_json, scraped_at)
         SELECT
             d->>'scraper_id',
             d->>'scraper_name',
             COALESCE(d->>'category', ''),
             d->>'target_url',
             COALESCE(d->>'url', d->>'target_url'),
             COALESCE(d->>'title', ''),
             COALESCE(d->>'content', ''),
             CASE WHEN d->>'published_at' IS NOT NULL AND d->>'published_at' != ''
                  THEN (d->>'published_at')::timestamptz ELSE NULL END,
             d,
             (d->>'scraped_at')::timestamptz
         FROM src
         ON CONFLICT (page_url, title, (COALESCE(published_at, '1970-01-01'::timestamptz)))
         DO UPDATE SET
             content = EXCLUDED.content,
             raw_json = EXCLUDED.raw_json,
             scraped_at = EXCLUDED.scraped_at;" 2>&1; then
        ROWS_OK=$((ROWS_OK + 1))
        printf '%s\n' "$line"
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
