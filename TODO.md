# TODO

## Pre-production cleanup
- [ ] Stop exposing internal service ports to host (conductor :8000, db :5432, db-restful :5000). All services should communicate via the `conscious-feed` Docker network internally. Only the UI should be outward-facing.
- [ ] Configure scripts to launch UI + backend together. Currently `launch.sh` skips scraper-ui.
- [ ] Clean up ad-hoc bash API calls (curl in `run_wrapper.sh`, `ingest.sh`). Inline JSON construction and `curl` fire-and-forget is fragile — consider a shared shell helper or a lightweight client script.
- [ ] Route `ingest.sh` DB writes through db-restful instead of direct psql. Needs a batch `/ingest` endpoint to avoid per-row HTTP overhead — the streaming pipeline is performance-sensitive.
