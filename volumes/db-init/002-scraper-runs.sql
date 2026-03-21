CREATE TABLE IF NOT EXISTS scraper_runs (
    id              BIGSERIAL PRIMARY KEY,
    scraper_id      TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    exit_code       INT,
    stderr_tail     TEXT NOT NULL DEFAULT '',
    rows_inserted   INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_scraper_runs_scraper_id ON scraper_runs (scraper_id);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs (scraper_id, started_at DESC);
