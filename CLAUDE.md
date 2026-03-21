# ConsciousFeed

AI-hybridized RSS bridge for the self-hosting era. Users define what data they want from the web in natural language; the system scrapes it into structured feeds, with AI agents that auto-fix broken scrapers.

## Project Structure

```
conscious_feed/
├── docker-compose.yml          # Root compose: conductor, db, shared network/volumes
├── fleet-conductor/            # Orchestration container (DinD + FastAPI)
│   ├── api.py                  # FastAPI server: add/edit/remove scrapers
│   ├── scraper_spec.py         # ScraperSpec + ScraperMonitoringSpec dataclasses
│   ├── cron.py                 # Builds/installs crontab from scraper schedules
│   ├── Dockerfile              # Python 3.11 + Docker CLI + Compose + cron
│   ├── entrypoint.sh           # Starts crond, then uvicorn
│   └── requirements.txt        # fastapi, uvicorn, pyyaml
├── hybrid-scraper/             # The scraper container image
│   ├── Dockerfile              # Python 3.11 + Node + Playwright + jq + psql
│   ├── entrypoint.sh           # Fleet-mode symlink, browser server, WS_ENDPOINT export, pipe to ingest.sh
│   ├── ingest.sh               # Reads JSONL from stdin, enriches, inserts into PostgreSQL
│   ├── scrape.py               # Original standalone scraper (hardcoded URL, legacy)
│   ├── playwright-server/      # Persistent Node.js browser server (survives script crashes)
│   └── sys_admin_controller/   # CLI cron manager (early prototype, may be superseded by fleet-conductor)
├── db-init/
│   └── 001-schema.sql          # PostgreSQL schema: scrape_results table
└── conscious-feed-pitch.html   # Pitch deck describing the vision
```

## Architecture

### Orchestration Flow
1. **Root compose** brings up `conductor` (FastAPI on :8000) and `db` (PostgreSQL on :5432) on the `conscious-feed` named network.
2. The conductor has the Docker socket mounted — it manages scraper containers by generating an internal compose file at `/app/fleet/docker-compose.yml`.
3. API calls to the conductor (`POST/PATCH/DELETE /scrapers`) create/modify ScraperSpec entries, which translate to compose service definitions.
4. Each scraper container mounts `fleet-shared` volume. On creation, the conductor writes a stub `scraper.py` to `/fleet-shared/<scraper_id>/`.
5. Scraper entrypoint symlinks `/app/scrape.py` → `/fleet-shared/<scraper_id>/scraper.py` when in fleet mode.

### Data Flow (scraper → database)
```
entrypoint.sh → starts browser server → exports WS_ENDPOINT
             → python3 scrape.py | ingest.sh
                    │                    │
                    │ JSONL to stdout     │ enriches with metadata
                    └────────────────────│ psql INSERT → db:5432
```
- **scrape.py** is maximally naive: reads `WS_ENDPOINT` and `TARGET_URL` from env, uses Playwright, outputs `{"url", "title", "content"}` JSON lines to stdout. No database awareness.
- **ingest.sh** handles all infra: enriches JSON with scraper_id/name/timestamp, inserts into `scrape_results` via `psql`.

### Key Design Decisions
- **ScraperSpec** (`scraper_spec.py`): user-facing dataclass with `scraper_id` (auto-generated, never user-supplied, incremental `scraper-001`, `scraper-002`...), `name`, `target_url`, `scraping_prompt`, `cron_schedule`. Translates to/from compose service definitions.
- **ScraperMonitoringSpec**: separate dataclass for live data (`health`, `last_run`, `total_runs`), optional field on ScraperSpec. Keeps static config separate from runtime state.
- **scraper_id is permanent**: fleet-shared directories are never deleted on scraper removal, since IDs are unique identifiers that should never be reused.
- **Shared named network** (`conscious-feed`): all containers (conductor, db, scrapers) share it. The fleet compose declares it as `external: true`.
- **Shared named volume** (`fleet-shared`): mounted in conductor and all scrapers. Conductor writes per-scraper scripts, scrapers read them.
- **Cron scheduling**: conductor's crond runs `docker compose run --rm <scraper_id>` on each scraper's `cron_schedule`. Rebuilt on every add/edit/remove.

### Database
- PostgreSQL 16 (Alpine), hostname `db` on the shared network.
- Single table `scrape_results`: id, scraper_id, scraper_name, target_url, page_url, title, content, raw_json (JSONB), scraped_at, created_at.
- DB credentials hardcoded for internal Docker network: `conscious_feed`/`conscious_feed`/`conscious_feed`.

## Exposed Ports

Only two ports are exposed to the host:
- **9200** — MCP proxy (`mcp_proxy`). This is the single interface for Claude Code to interact with the system.
- **5173** — Scraper UI (`scraper_ui`).

All other services (conductor, db, db-restful) communicate internally on the `conscious-feed` Docker network. **Do not add host port mappings for internal services.**

## MCP Proxy (`mcp_proxy`, port 9200)

The MCP proxy is a persistent FastMCP server that acts as the single gateway for Claude Code. It exposes tools covering all conductor and db-restful endpoints, plus forwarding to active dev-agent repair containers. Claude Code should use MCP tools exclusively — no curl to internal services.

Configured in `.mcp.json` and auto-approved via `.claude/settings.local.json`.

### Debugging without host ports

If you need to manually curl an internal API for debugging, exec into the `mcp_proxy` container (it has `curl` installed and is on the `conscious-feed` network):

```bash
docker exec mcp_proxy curl -s http://conductor:8000/scrapers
docker exec mcp_proxy curl -s http://restful_db:5000/rss_content
```

## API (fleet-conductor, internal only)

- `GET /health`
- `GET /scrapers` — list all scrapers with monitoring and container state
- `GET /scrapers/{scraper_id}` — single scraper detail
- `POST /scrapers` — body: `{name?, target_url, scraping_prompt, cron_schedule?, autorepair?}`
- `PATCH /scrapers/{scraper_id}` — body: `{name?, target_url?, scraping_prompt?, cron_schedule?, autorepair?}`
- `DELETE /scrapers/{scraper_id}`
- `POST /scrapers/{scraper_id}/run` — manual trigger
- `POST /scrapers/{scraper_id}/launch_debug` — debug mode with live browser
- `POST /scrapers/{scraper_id}/stop` — stop and clean up
- `POST /scrapers/{scraper_id}/repair` — body: `{lazy?, sockpuppet?}` — launch dev-agent repair
- `GET /scrapers/repair-candidates` — failing scrapers with autorepair enabled
- `GET /repair-containers` — active repair containers
- `POST /batch-update` — bulk scraper upsert

## Status / What's Next

### Current State (rough assembly)
- The pipeline is structurally complete but untested end-to-end in containers.
- `scraping_prompt` is passed as an env var but not yet consumed by anything — this is where AI-generated scraper logic will plug in.
- `sys_admin_controller/` in hybrid-scraper is an early prototype that predates fleet-conductor and may be removed.
- **hybrid-scraper** is closest to workable — minimalist enough that there's not much to go wrong. Will get harder as we validate the sysadmin loop and add more optionalities for agents to interact.
- **fleet-conductor** needs a serious refactor. The logic is sound but the code quality is at saturation for velocity — human needs to go back and direct sanitisation before building further on top of it.

### Milestone 1: Main Loop (next priority)
Get 1-2 example scraper scripts for testing. Launching orchestrator + database should be sufficient for RSS-like JSON artifacts from those websites to slowly plumb their way into the database. At that point we have a real main loop to iterate on.

### Milestone 2: AI Agent Development
- Start by exposing pipes or other entrypoints for a human-guided Claude to debug or implement scripts — verify that the tools and scaffolding placed to make that easier actually work well.
- OpenCode agents are the real goal but need careful rollout due to costs. Needs thought on how they should puppet a hybrid scraper.
- Likely want an orchestrator API endpoint where agents can request a 'debug' run of a broken scraper, so they can look inside and experiment using the Playwright server from the exact moment that the script fails.

### Milestone 3: UI
- **RSS content display**: should be straightforward — render scraped content from the database in a clean feed view.
- **Config section**: glorified spreadsheet (website name, URL, prompt) with an update button to send API requests to orchestrator or agents. Not complex.
- **Fleet visualisation**: hardest and coolest part — a live view of the scraping/AI-dev fleet, showing container states, agent activity, failure recovery in real time.
