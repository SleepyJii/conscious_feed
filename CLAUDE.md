# ConsciousFeed

AI-hybridized RSS bridge for the self-hosting era. Users define what data they want from the web in natural language; the system scrapes it into structured feeds, with AI agents that auto-fix broken scrapers.

## Project Structure

```
conscious_feed/
├── docker-compose.yml              # Root compose: all services + build-only images
├── config.json                     # Local secrets (gitignored, copy from config.example.json)
├── config.example.json             # Template for config.json
├── .mcp.json                       # MCP server config for Claude Code
├── .claude/
│   ├── settings.local.json         # Claude Code permissions (auto-approve MCP tools)
│   └── skills/
│       ├── conscious-feed/         # Master health check + repair loop
│       ├── repair-scraper/         # Single scraper repair via MCP tools
│       └── check-repair-candidates/# Fleet health overview
├── containers/
│   ├── fleet-conductor/            # Orchestration (FastAPI + Docker socket + cron)
│   │   ├── server.py               # API endpoints
│   │   ├── scraper_spec.py         # ScraperSpec dataclass
│   │   ├── fleet.py                # ID generation, stub scripts, cron sync
│   │   ├── state_helpers/          # Compose YAML + crontab management
│   │   ├── api_helpers/            # Monitoring queries + event emission
│   │   ├── run_wrapper.sh          # Cron wrapper: runs scraper, records result
│   │   └── launch-repairs.sh       # Cron wrapper: triggers repairs for failing scrapers
│   ├── hybrid-scraper/             # Scraper container image
│   │   ├── entrypoint.sh           # Starts browser server, runs scrape.py | ingest.sh
│   │   ├── ingest.sh               # JSONL stdin → PostgreSQL
│   │   └── playwright-server/      # Node.js browser server (persists across script crashes)
│   ├── dev-agent/                  # AI repair agent container
│   │   ├── mcp_server.py           # FastMCP server (browser tools, script R/W, test)
│   │   ├── repair.py               # Autonomous repair via Claude Agent SDK
│   │   ├── entrypoint.sh           # Sockpuppet=MCP server, else=repair.py
│   │   └── MCP_SPEC.md             # Tool spec + scraper contract documentation
│   ├── mcp-proxy/                  # Persistent MCP gateway for Claude Code
│   │   └── mcp_proxy.py            # Forwards tool calls to conductor/db-restful/dev-agents
│   ├── db-restful/                 # REST API over PostgreSQL (events, content)
│   └── scraper-ui/                 # React frontend
├── volumes/
│   ├── fleet-data/                 # Bind-mounted: per-scraper dirs, fleet compose
│   ├── db-init/                    # SQL schema files
│   └── postgres_data/              # PostgreSQL data
└── scripts/
    ├── build.sh                    # Build all images (sources config for API key)
    ├── launch.sh                   # Source config + docker compose up
    ├── relaunch.sh                 # Down + build + up
    ├── load_config.sh              # Export config.json keys as env vars
    └── wipeclean-data.sh           # Reset volumes
```

## Architecture

### Services (root compose)

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| conductor | conductor | internal | Fleet orchestration API, cron, Docker socket |
| db | postgres_db | internal | PostgreSQL 16 |
| db-restful | restful_db | internal | REST API for events + scraped content |
| scraper-ui | scraper_ui | **5173** | React frontend |
| mcp-proxy | mcp_proxy | **9200** | MCP gateway for Claude Code |
| hybrid-scraper | (build-only) | — | Scraper container image |
| dev-agent | (build-only) | — | Repair agent image |

### Exposed Ports

Only two ports are exposed to the host:
- **9200** — MCP proxy. Single interface for Claude Code.
- **5173** — Scraper UI.

All other services communicate internally on the `conscious-feed` Docker network. **Do not add host port mappings for internal services.**

### Data Flow (scraper → database)
```
entrypoint.sh → starts browser server → exports WS_ENDPOINT
             → python3 scrape.py | ingest.sh
                    │                    │
                    │ JSONL to stdout     │ enriches with metadata
                    └────────────────────│ psql INSERT → db:5432
```

### Fleet Compose (dynamic)

The conductor manages a separate compose file at `/fleet-data/docker-compose.yml` under project name `fleet`. All dynamically launched containers (scrapers, debug instances, repair agents) are services in this file. Clean up with `docker compose -p fleet down`.

### Repair Pipeline

1. **Cron loop** (`launch-repairs.sh`): every N minutes, finds failing scrapers with `autorepair=True`, calls `/repair` endpoint
2. **Repair endpoint**: launches a debug scraper (live browser) + dev-agent (MCP server or autonomous repair)
3. **Sockpuppet mode** (`SOCKPUPPET=1`): dev-agent runs MCP server on :8080, Claude Code connects via mcp-proxy to diagnose interactively
4. **Autonomous mode**: dev-agent runs `repair.py` using Claude Agent SDK, connects to its own MCP server, fixes the script, exits

### Key Design Decisions
- **ScraperSpec**: `scraper_id` is auto-generated, permanent, never reused. Fields: name, target_url, scraping_prompt, cron_schedule, autorepair.
- **Stub scripts**: new scrapers get a `NotImplementedError` stub — repair agents implement them from scratch using the `scraping_prompt`.
- **ANTHROPIC_API_KEY**: baked into the dev-agent image at build time via build arg (sourced from `config.json`). Conductor never touches it.
- **MCP proxy pattern**: always-running proxy so Claude Code sees tools on startup. Forwards to transient dev-agent containers by Docker hostname (`repair-{scraper_id}:8080`).

## MCP Proxy (`mcp_proxy`, port 9200)

The MCP proxy is the single gateway for Claude Code. It exposes tools for:
- **Conductor API**: scraper CRUD, run/stop/debug/repair, monitoring
- **DB-Restful API**: scraped content, event log
- **Dev-agent forwarding**: browser tools, script R/W, test execution

Configured in `.mcp.json` and auto-approved via `.claude/settings.local.json` (`mcp__conscious-feed-tools__*`).

### Debugging without host ports

Exec into the `mcp_proxy` container (it has `curl` and is on the `conscious-feed` network):

```bash
docker exec mcp_proxy curl -s http://conductor:8000/scrapers
docker exec mcp_proxy curl -s http://restful_db:5000/rss_content
```

## API (fleet-conductor, internal only)

- `GET /health`
- `GET /scrapers` — list all with monitoring + container state
- `GET /scrapers/{scraper_id}` — single scraper detail
- `GET /scrapers/repair-candidates` — failing scrapers with autorepair
- `GET /repair-containers` — active repair containers
- `POST /scrapers` — body: `{name?, target_url, scraping_prompt, cron_schedule?, autorepair?}`
- `PATCH /scrapers/{scraper_id}` — partial update
- `DELETE /scrapers/{scraper_id}` — stop and remove
- `POST /scrapers/{scraper_id}/run` — manual trigger (via run_wrapper.sh)
- `POST /scrapers/{scraper_id}/launch_debug` — debug mode with live browser
- `POST /scrapers/{scraper_id}/stop` — stop + clean up debug/repair containers
- `POST /scrapers/{scraper_id}/repair` — body: `{lazy?, sockpuppet?}`
- `POST /batch-update` — bulk scraper upsert

## Database

- PostgreSQL 16, hostname `db` on the shared network.
- `scrape_results`: id, scraper_id, scraper_name, target_url, page_url, title, content, raw_json (JSONB), scraped_at, created_at
- `scraper_runs`: id, scraper_id, started_at, finished_at, exit_code, stderr_tail, rows_inserted
- DB credentials: `conscious_feed`/`conscious_feed`/`scrape_db` (internal Docker network only)

## Status / What's Next

### Current State
- Main scraping loop works end-to-end: conductor → cron → hybrid-scraper → ingest → PostgreSQL
- Repair pipeline structurally complete: cron detection → debug launch → dev-agent MCP server → sockpuppet repair via Claude Code skills
- Autonomous repair (`repair.py` via Claude Agent SDK) implemented but blocked on cost controls — needs repair budget/throttling before enabling
- MCP proxy operational: all conductor + db-restful endpoints exposed as tools, dev-agent forwarding works
- UI functional with scraper config + feed view

### Next Steps
- Schema changes to support more sophisticated repair strategies and cost tracking
- Repair budget/throttling to prevent runaway API costs from autonomous agents
- Fleet visualisation in UI: live container states, agent activity, repair history
