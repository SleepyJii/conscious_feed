# Dev-Agent MCP Server

MCP server running inside repair containers. Exposes tools for diagnosing and fixing broken scraper scripts. Accessed via the mcp-proxy, not directly.

## Transport

Streamable HTTP on `0.0.0.0:8080`. Reachable on the `conscious-feed` Docker network as `repair-{scraper_id}:8080`.

## Environment Variables (set by conductor)

| Var | Description |
|-----|-------------|
| `SCRAPER_ID` | e.g. `scraper-001` |
| `TARGET_URL` | URL the scraper targets |
| `SCRAPING_PROMPT` | User's natural-language description of what to extract |
| `SCRAPER_DIR` | `/fleet-data/{scraper_id}` — contains `scraper.py`, `last_error.txt` |
| `WS_ENDPOINT` | WebSocket URL to the debug scraper's live Playwright browser |
| `SOCKPUPPET` | Set to `1` to start MCP server instead of running `repair.py` |

## Tools

### `get_scraper_info()`
Returns all env vars, contents of `last_error.txt`, and current `scraper.py`. No parameters. First tool to call when starting a repair.

### `browse_page(url, javascript?)`
Connects to the debug scraper's browser via `WS_ENDPOINT`, navigates to `url`, returns page title, final URL, body text. Optional `javascript` param runs `page.evaluate()`.

### `test_selector(url, selector)`
Navigates to `url`, runs `query_selector_all(selector)`, returns match count and first 20 elements with tag, text, and key attributes (href, src, class).

### `read_scraper_script()`
Returns contents of `{SCRAPER_DIR}/scraper.py`.

### `write_scraper_script(content)`
Writes `content` to `{SCRAPER_DIR}/scraper.py`. Since fleet-data is bind-mounted, the change is immediately visible on the host.

### `test_scraper_script()`
Runs `scraper.py` as a subprocess with `WS_ENDPOINT` and `TARGET_URL` set, connecting to the debug scraper's live browser. Returns stdout, stderr, exit_code. 60s timeout.

## Scraper Script Contract

Scripts written via `write_scraper_script` must:
- Read `WS_ENDPOINT` and `TARGET_URL` from env
- Connect via `p.chromium.connect(ws)` (NOT `launch()`)
- Output `{"url", "title", "content"}` JSONL to stdout
- Not interact with the database (ingest.sh handles that)

## Repair Workflow

1. `get_scraper_info()` — understand the problem
2. `browse_page(target_url)` — see the live page
3. `test_selector(target_url, selector)` — iterate on selectors
4. `write_scraper_script(fixed_script)` — write the fix
5. `test_scraper_script()` — verify it works
6. Repeat 3-5 as needed
