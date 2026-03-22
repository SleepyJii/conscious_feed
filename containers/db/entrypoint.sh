#!/bin/bash
# Wrapper entrypoint: starts postgres, then applies retention config on every boot.
set -e

# Start the stock postgres entrypoint in the background
docker-entrypoint.sh postgres -c shared_preload_libraries=pg_cron -c cron.database_name=scrape_db &
PG_PID=$!

# Wait for postgres to accept connections AND the target database to exist
# (on first init, docker-entrypoint.sh creates the DB before starting postgres)
until psql -U "${POSTGRES_USER:-conscious_feed}" -d "${POSTGRES_DB:-scrape_db}" -c "SELECT 1" >/dev/null 2>&1; do
    sleep 1
done

# Apply retention jobs (pg_cron upserts by job name, so this is idempotent)
CONTENT_DAYS="${RETENTION_CONTENT_DAYS:-30}"
RUNS_DAYS="${RETENTION_RUNS_DAYS:-90}"
EVENTS_DAYS="${RETENTION_EVENTS_DAYS:-14}"

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q <<SQL
CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule('retention-scrape-results', '0 3 * * *',
    \$\$DELETE FROM scrape_results WHERE scraped_at < now() - interval '${CONTENT_DAYS} days'\$\$);

SELECT cron.schedule('retention-scraper-runs', '0 3 * * *',
    \$\$DELETE FROM scraper_runs WHERE started_at < now() - interval '${RUNS_DAYS} days'\$\$);

SELECT cron.schedule('retention-events', '0 3 * * *',
    \$\$DELETE FROM events WHERE created_at < now() - interval '${EVENTS_DAYS} days'\$\$);

SELECT cron.schedule('retention-vacuum', '30 3 * * *',
    \$\$VACUUM ANALYZE scrape_results; VACUUM ANALYZE scraper_runs; VACUUM ANALYZE events\$\$);
SQL

echo "pg_cron retention applied: content=${CONTENT_DAYS}d, runs=${RUNS_DAYS}d, events=${EVENTS_DAYS}d"

# Wait on postgres as the main process
wait $PG_PID
