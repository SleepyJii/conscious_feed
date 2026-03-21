# ConsciousFeed

**AI-hybridized RSS Bridges, for the self hosted data monger**

Tell it what data you want from the web in plain English. It scrapes it into structured feeds. When scrapers break, AI agents fix them automatically.

## How It Works

1. You describe what you want scraped (URL + natural language prompt)
2. The **fleet conductor** spins up a scraper container with a Playwright browser
3. The scraper outputs JSON to stdout; a bash ingestion layer handles database writes
4. Results land in PostgreSQL as queryable, RSS-like feed items
5. Scrapers run on cron schedules — when one breaks, AI agents diagnose and repair it using the live browser session

## Quick Start

```bash
# Bring up the conductor + database
docker compose up -d

# Add a scraper
curl -X POST localhost:8000/scrapers \
  -H 'Content-Type: application/json' \
  -d '{"target_url": "https://example.com", "scraping_prompt": "extract article titles and content"}'

# Check what's running
curl localhost:8000/scrapers

# Remove a scraper
curl -X DELETE localhost:8000/scrapers/scraper-001
```

## Architecture

```
docker-compose.yml
├── conductor (:8000)    FastAPI orchestrator — manages scraper fleet via Docker-in-Docker
├── db (:5432)           PostgreSQL — stores all scraped content
└── scraper-NNN          Dynamically created per-scraper containers (hybrid-scraper image)
```

All services share the `conscious-feed` Docker network. Scrapers are ephemeral containers managed by the conductor through a generated internal compose file.

### Data Pipeline

```
scrape.py → JSONL to stdout → ingest.sh → PostgreSQL
```

Scraper scripts are intentionally naive — they only know about Playwright and printing JSON. The bash wrapper (`ingest.sh`) handles metadata enrichment and database writes, keeping the Python maximally simple for AI-generated code.

### Key Components

| Component | Role |
|-----------|------|
| **fleet-conductor** | FastAPI + Docker CLI. Manages scraper lifecycle, generates compose files, handles cron scheduling |
| **hybrid-scraper** | Container image with Playwright (Node.js browser server + Python client). Each instance runs one scraper script |
| **ingest.sh** | Bash layer between scraper output and database. Reads JSONL, enriches with metadata, inserts via psql |
| **fleet-shared** volume | Conductor writes per-scraper scripts here; scraper containers symlink to them at startup |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/scrapers` | Create a new scraper (auto-assigns ID) |
| PATCH | `/scrapers/{id}` | Update scraper config |
| DELETE | `/scrapers/{id}` | Remove a scraper |

### Create Scraper Body

```json
{
  "name": "My Blog Scraper",
  "target_url": "https://example.com/blog",
  "scraping_prompt": "extract all article titles and summaries",
  "cron_schedule": "0 */6 * * *"
}
```

All fields except `target_url` and `scraping_prompt` are optional. `scraper_id` is auto-generated (`scraper-001`, `scraper-002`, ...) and never reused.

## Requirements

- Docker with Compose plugin
- That's it

## WIP

This project is under active development. The structural pipeline (conductor, scraper containers, database, ingestion) is assembled but not yet validated end-to-end. Current priorities:

- **Next up**: Get example scrapers running and confirm data flows from web page to database rows
- **Then**: Expose tooling for AI agents to debug and write scraper scripts against live browser sessions
- **Later**: Web UI for browsing feeds, configuring scrapers, and visualising the fleet in real time
