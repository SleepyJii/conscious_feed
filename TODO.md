# TODO

## Pre-production cleanup
- [ ] Stop exposing internal service ports to host (conductor :8000, db :5432, db-restful :5000). All services should communicate via the `conscious-feed` Docker network internally. Only the UI should be outward-facing.
- [ ] Configure scripts to launch UI + backend together. Currently `launch.sh` skips scraper-ui.
