CREATE TABLE IF NOT EXISTS events (
    event_id        BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          TEXT NOT NULL,
    container_id    TEXT,
    event_type      TEXT NOT NULL,
    event_payload   JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_source ON events (source);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_container_id ON events (container_id);
