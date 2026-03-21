# TODO

## Architecture
- [x] ~~Clearer reasoning about temporary containers~~ — dev-agents are now added as services in the fleet compose (`docker compose -p fleet`), so `docker compose -p fleet down` cleans everything up.

## Pre-publish
- [ ] Sync MCP tool definitions between `containers/dev-agent/MCP_SPEC.md`, `containers/mcp-proxy/mcp_proxy.py`, and `.claude/skills/` before publishing. Any tool changes in the dev-agent server must be reflected in the proxy and skill descriptions.

## Pre-production cleanup
- [x] ~~Stop exposing internal service ports to host~~ — only UI (:5173) and MCP proxy (:9200) are exposed. Internal services communicate via Docker network.
- [x] ~~Configure scripts to launch UI + backend together.~~ — `launch.sh` now launches all services.
- [ ] Clean up ad-hoc bash API calls (curl in `run_wrapper.sh`, `ingest.sh`). Inline JSON construction and `curl` fire-and-forget is fragile — consider a shared shell helper or a lightweight client script.
- [ ] Route `ingest.sh` DB writes through db-restful instead of direct psql. Needs a batch `/ingest` endpoint to avoid per-row HTTP overhead — the streaming pipeline is performance-sensitive.
