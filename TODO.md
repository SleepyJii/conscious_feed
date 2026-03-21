# TODO

## Architecture
- [ ] Clearer reasoning about temporary containers (debug runs, dev-agents). These are launched via raw `docker run` outside any compose file, so the conductor has no first-class way to track them — it relies on `docker ps` name filtering against the same daemon it's running on. Need a proper tracking mechanism: could be a lightweight registry in the DB, a state file in fleet-data, or putting transient containers into a dedicated compose file. Related: cleanup/reaping of stale containers, concurrency limits, and making the stop endpoint aware of all container types.

## Pre-production cleanup
- [ ] Stop exposing internal service ports to host (conductor :8000, db :5432, db-restful :5000). All services should communicate via the `conscious-feed` Docker network internally. Only the UI should be outward-facing.
- [ ] Configure scripts to launch UI + backend together. Currently `launch.sh` skips scraper-ui.
- [ ] Clean up ad-hoc bash API calls (curl in `run_wrapper.sh`, `ingest.sh`). Inline JSON construction and `curl` fire-and-forget is fragile — consider a shared shell helper or a lightweight client script.
- [ ] Route `ingest.sh` DB writes through db-restful instead of direct psql. Needs a batch `/ingest` endpoint to avoid per-row HTTP overhead — the streaming pipeline is performance-sensitive.
