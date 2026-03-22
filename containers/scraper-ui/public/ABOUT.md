# Conscious Feed

AI-hybridized RSS bridge for the self-hosting era. Define what data you want from the web in natural language — the system scrapes it into structured feeds, with AI agents that auto-fix broken scrapers.

## How It Works

You create **scraper specs** that describe a target URL and what you want extracted, in plain English. The system handles the rest: it deploys a headless browser, runs your scraper on a cron schedule, and pipes the results into a database. When a scraper breaks (and they do — websites change), AI repair agents diagnose the problem and rewrite the script automatically.

## Pages

### Feed
Your aggregated content stream. All scraped items appear here in reverse chronological order, sorted by publish date when available. Filter by source, search across titles and content, or load more items as needed.

### FleetControl
Operational dashboard for the scraper fleet. The top row shows:
- **Scraper Health** — pie chart of healthy, degraded, failing, and pending scrapers
- **Fleet Timeline** — minute-level graph of total scraper specs (white dashed), active scrapers (blue), and active repair agents (red)
- **Recent Events** — latest system events

Below is the scraper table with per-row action buttons:
- **Play** — trigger a manual scraper run
- **Stop** — kill running containers (scraper, debug, or repair)
- **Wrench** — launch a repair agent with a model name, or in sockpuppet mode for interactive debugging

### Configure
Opens the scraper config editor. Switch between a visual GUI (accordion list of all scrapers) and raw JSON mode. Add new scrapers with the **+** button, edit any field, or remove scrapers. Each scraper has:
- **Name** — human-readable label
- **Target URL** — the page to scrape
- **Scraping Prompt** — natural-language description of what to extract
- **Cron Schedule** — how often to run (e.g. `*/30 * * * *` for every 30 minutes)
- **Repair Policy** — comma-separated steps for failure handling

## Repair Policy

The repair policy controls what happens on consecutive failures:

| Keyword | Behavior |
|---------|----------|
| `RETRY` | Run the scraper again on the next cron cycle |
| `REPAIR:<model>` | Launch an AI repair agent using the specified model (e.g. `haiku`, `sonnet`, or a full model ID) |
| `STALL` | Stop running until a human intervenes |

The policy is a sequence — each consecutive failure advances one step. The last step repeats forever. Examples:

- `RETRY` — retry forever, never repair or stall
- `RETRY, REPAIR:haiku, STALL` — retry once, try a haiku repair, then stall
- `RETRY, RETRY, REPAIR:haiku, REPAIR:sonnet, STALL` — two retries, then escalate through models before stalling

A successful repair resets the failure counter back to the beginning.

## Typical Usage Flow

1. Open **Configure** and click **+ Add Scraper**
2. Fill in a target URL and describe what you want in the scraping prompt
3. Set a cron schedule and a repair policy (the default `RETRY, REPAIR:haiku, STALL` is sensible)
4. Save — the scraper deploys with a stub script that will fail on first run
5. The repair policy kicks in: after the initial failures, an AI agent implements the scraper from scratch
6. Once repaired, the scraper runs on schedule and content appears in the **Feed**
7. If the target site changes and the scraper breaks again, the policy handles it automatically

For hands-on debugging, use the **Wrench** button in FleetControl with sockpuppet mode — this gives you an interactive MCP connection to the repair agent's browser and tools.

## RSS Endpoint

Conscious Feed serves a standard RSS 2.0 XML feed at `/rss`, compatible with any RSS reader (Feedly, Miniflux, Newsboat, etc).

**Base URL:** `http://<host>:5173/rss`

**Query parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `source` | Filter by scraper ID | `?source=scraper-001` |
| `category` | Filter by category label | `?category=blogs` |
| `search` | Full-text search across titles and content | `?search=china` |
| `limit` | Max items returned (default 50) | `?limit=25` |

Parameters can be combined: `?category=finance&limit=10` or `?source=scraper-002&search=market`.

This is what makes Conscious Feed an RSS bridge — point any feed reader at a filtered `/rss` URL and get a live, self-healing feed from any website, even those that don't offer RSS natively.
