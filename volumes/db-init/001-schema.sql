CREATE TABLE IF NOT EXISTS scrape_results (
    id             BIGSERIAL PRIMARY KEY,
    scraper_id     TEXT NOT NULL,
    scraper_name   TEXT NOT NULL DEFAULT '',
    target_url     TEXT NOT NULL DEFAULT '',
    page_url       TEXT NOT NULL DEFAULT '',
    title          TEXT NOT NULL DEFAULT '',
    content        TEXT NOT NULL DEFAULT '',
    published_at   TIMESTAMPTZ,
    raw_json       JSONB NOT NULL DEFAULT '{}',
    scraped_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scrape_results_scraper_id ON scrape_results (scraper_id);
CREATE INDEX IF NOT EXISTS idx_scrape_results_scraped_at ON scrape_results (scraped_at);

-- Dedup: same article from the same scraper is upserted, not duplicated
CREATE UNIQUE INDEX IF NOT EXISTS idx_scrape_results_dedup
    ON scrape_results (page_url, title, COALESCE(published_at, '1970-01-01'::timestamptz));
