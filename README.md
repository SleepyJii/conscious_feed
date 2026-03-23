# ConsciousFeed

**AI-hybridized RSS bridges for the self-hosting era**

Tell it what data you want from the web in plain English. It scrapes it into structured feeds. When scrapers break, AI agents fix them automatically.

[Demo Video](https://youtu.be/B1ozqhL2l7I)

## How It Works

1. You describe what you want scraped (URL + natural language prompt)
2. The **fleet conductor** spins up a scraper container with a Playwright browser
3. The scraper outputs JSONL to stdout; a bash ingestion layer handles database writes
4. Results land in PostgreSQL as queryable, deduplicated feed items
5. Scrapers run on cron schedules — when one breaks, AI repair agents diagnose and fix it using a live browser session
6. A **React UI** lets you browse feeds, configure scrapers, and monitor fleet health
7. An **MCP proxy** exposes the entire system as tools for Claude Code

## Quick Start

```bash
# Copy config and add your Anthropic API key (needed for repair agents)
cp config.example.json config.json

# Build all images and bring everything up
scripts/build.sh
scripts/launch.sh
```

- **UI**: http://localhost:5173
- **MCP proxy**: localhost:9200 (configured in `.mcp.json` for Claude Code)

All internal services communicate on the `conscious-feed` Docker network. Only the UI and MCP proxy are exposed to the host.

## Architecture

```
docker-compose.yml
├── conductor          Fleet orchestrator — FastAPI + Docker socket + cron
├── db                 PostgreSQL 16 with pg_cron retention policies
├── db-restful         REST API over PostgreSQL (events, content, RSS/JSON/YAML feeds)
├── scraper-ui         React frontend (feed browser + scraper config)
├── mcp-proxy          MCP gateway for Claude Code (forwards to all services)
├── hybrid-scraper     (build-only) Scraper container image
└── dev-agent          (build-only) AI repair agent image
```

Dynamic containers (scrapers, debug instances, repair agents) are managed by the conductor via a separate compose file under the `fleet` project.

### Data Pipeline

```
entrypoint.sh → browser server (Node.js, persists across crashes)
             → python3 scrape.py → JSONL to stdout
             → ingest.sh → metadata enrichment → psql INSERT → PostgreSQL
```

Scraper scripts are intentionally simple — they connect to a Playwright browser via WebSocket, scrape data, and print JSON lines. The bash wrapper handles everything else.

### Self-Healing Repair Pipeline

1. **Cron detection**: `launch-repairs.sh` finds scrapers with consecutive failures whose repair policy says `REPAIR:<model>`
2. **Debug + agent launch**: Conductor spins up a debug scraper (live browser) and a dev-agent container
3. **Autonomous repair**: The dev-agent uses Claude Agent SDK to diagnose the failure, browse the target site, fix the script, and test it
4. **Sockpuppet mode**: Alternatively, the dev-agent runs as an MCP server so Claude Code can interactively diagnose via the MCP proxy

### Operational Safety

- **Per-scraper run timeouts** with `timeout` command in wrapper scripts
- **Global repair timeout** for dev-agent containers
- **Database retention** via pg_cron (configurable days for content, runs, events)
- **Docker log rotation** on all services (10MB, 3 files)
- **Memory/CPU limits** on dynamic containers (512MB for scrapers, 1GB for repair agents)
- **Trap handlers** in wrapper scripts for cleanup on signal/crash
- **Restart policies** on all long-running services

## Configuration

All config lives in `config.json` (gitignored). See `config.example.json`:

```json
{
  "ANTHROPIC_API_KEY": "sk-ant-your-key-here",
  "MODEL_ALIASES": {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6"
  },
  "REPAIR_CRON_SCHEDULE": "* * * * *",
  "MAX_CONCURRENT_REPAIRS": "1",
  "REPAIR_TIMEOUT": "900",
  "RETENTION_CONTENT_DAYS": "30",
  "RETENTION_RUNS_DAYS": "90",
  "RETENTION_EVENTS_DAYS": "14"
}
```

## API

The conductor API is internal-only (no host port). Interact via the MCP proxy or UI.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/scrapers` | List all scrapers with monitoring + container state |
| GET | `/scrapers/{id}` | Single scraper detail |
| POST | `/scrapers` | Create a new scraper |
| PATCH | `/scrapers/{id}` | Update scraper config |
| DELETE | `/scrapers/{id}` | Remove a scraper |
| POST | `/scrapers/{id}/run` | Manually trigger a run |
| POST | `/scrapers/{id}/repair` | Launch repair agent |
| POST | `/scrapers/{id}/stop` | Stop + clean up containers |

### Create Scraper Body

```json
{
  "name": "My Hackathon Feed",
  "target_url": "https://example.com/events",
  "scraping_prompt": "extract event names, dates, and links",
  "cron_schedule": "17 4 * * 3",
  "repair_policy": ["RETRY", "REPAIR:haiku", "REPAIR:sonnet", "STALL"],
  "category": "hackathons",
  "run_timeout": 300
}
```

## Requirements

- Docker with Compose plugin
- An Anthropic API key (for repair agents)

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/build.sh` | Build all Docker images |
| `scripts/launch.sh` | Source config + docker compose up |
| `scripts/relaunch.sh` | Down + build + up |
| `scripts/wipeclean-data.sh` | Reset all volumes |
