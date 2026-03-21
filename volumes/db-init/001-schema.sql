CREATE TABLE IF NOT EXISTS scrape_results (
    id           BIGSERIAL PRIMARY KEY,
    scraper_id   TEXT NOT NULL,
    scraper_name TEXT NOT NULL DEFAULT '',
    target_url   TEXT NOT NULL DEFAULT '',
    page_url     TEXT NOT NULL DEFAULT '',
    title        TEXT NOT NULL DEFAULT '',
    content      TEXT NOT NULL DEFAULT '',
    raw_json     JSONB NOT NULL DEFAULT '{}',
    scraped_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scrape_results_scraper_id ON scrape_results (scraper_id);
CREATE INDEX IF NOT EXISTS idx_scrape_results_scraped_at ON scrape_results (scraped_at);
