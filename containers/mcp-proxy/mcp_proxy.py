"""
MCP proxy — the single interface for Claude Code to interact with ConsciousFeed.

Exposes tools for:
- Conductor API (scraper management, repair, monitoring)
- DB-Restful API (scraped content, events)
- Dev-agent forwarding (browser tools for active repairs)

Always running so Claude Code sees it on startup. Lives on the conscious-feed
Docker network, so it can reach all internal services by hostname.
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

mcp = FastMCP("conscious-feed-tools", host="0.0.0.0", port=8080)

CONDUCTOR = "http://conductor:8000"
DB_RESTFUL = "http://restful_db:5000"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _api_call(base: str, method: str, path: str, body: dict | None = None) -> dict | list | str:
    """Make an HTTP request to an internal service."""
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            return {"error": json.loads(error_body).get("detail", error_body)}
        except json.JSONDecodeError:
            return {"error": f"HTTP {e.code}: {error_body[:500]}"}
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach {url}: {e.reason}"}


def _conductor(method: str, path: str, body: dict | None = None):
    return _api_call(CONDUCTOR, method, path, body)


def _db_restful(method: str, path: str, body: dict | None = None):
    return _api_call(DB_RESTFUL, method, path, body)


async def _call_dev_agent(scraper_id: str, tool_name: str, arguments: dict | None = None):
    """Forward a tool call to the dev-agent MCP server in repair-{scraper_id}."""
    url = f"http://repair-{scraper_id}:8080/mcp"
    try:
        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})
                if result.content:
                    for block in result.content:
                        if block.type == "text":
                            try:
                                return json.loads(block.text)
                            except json.JSONDecodeError:
                                return block.text
                return {"error": "Empty response from dev-agent"}
    except Exception as e:
        return {"error": f"Cannot reach repair-{scraper_id}: {e}. Is the repair container running?"}


# ---------------------------------------------------------------------------
# Conductor: health & status
# ---------------------------------------------------------------------------

@mcp.tool()
def check_health() -> dict:
    """Check if the conductor API is healthy."""
    return _conductor("GET", "/health")


@mcp.tool()
def list_scrapers() -> list:
    """List all scrapers with their config, health, and container state."""
    return _conductor("GET", "/scrapers")


@mcp.tool()
def get_scraper(scraper_id: str) -> dict:
    """Get a single scraper's config, health, and container state.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return _conductor("GET", f"/scrapers/{scraper_id}")


@mcp.tool()
def list_repair_candidates() -> dict:
    """List scrapers whose current repair_policy step is a REPAIR action."""
    return _conductor("GET", "/scrapers/repair-candidates")


@mcp.tool()
def list_repair_containers() -> dict:
    """List active repair containers with their status."""
    return _conductor("GET", "/repair-containers")


# ---------------------------------------------------------------------------
# Conductor: scraper management
# ---------------------------------------------------------------------------

@mcp.tool()
def add_scraper(
    target_url: str,
    scraping_prompt: str,
    name: str = "",
    cron_schedule: str = "",
    repair_policy: list[str] | None = None,
    agent_notes: str = "SCRAPER NOT YET IMPLEMENTED",
) -> dict:
    """Deploy a new scraper to the fleet.

    Args:
        target_url: URL the scraper should target
        scraping_prompt: Natural-language description of what to scrape
        name: Human-readable name (defaults to generated ID)
        cron_schedule: Cron expression, e.g. '*/30 * * * *'
        repair_policy: Ordered steps on consecutive failures: RETRY, STALL, REPAIR:<model>
        agent_notes: Short notes from repair agents about implementation details
    """
    return _conductor("POST", "/scrapers", {
        "name": name,
        "target_url": target_url,
        "scraping_prompt": scraping_prompt,
        "cron_schedule": cron_schedule,
        "repair_policy": repair_policy or ["RETRY"],
        "agent_notes": agent_notes,
    })


@mcp.tool()
def edit_scraper(
    scraper_id: str,
    name: str | None = None,
    target_url: str | None = None,
    scraping_prompt: str | None = None,
    cron_schedule: str | None = None,
    repair_policy: list[str] | None = None,
    agent_notes: str | None = None,
) -> dict:
    """Edit a scraper's config. Only provided fields are updated.

    Args:
        scraper_id: e.g. 'scraper-001'
        name: Human-readable name
        target_url: URL to scrape
        scraping_prompt: What to extract
        cron_schedule: Cron expression
        repair_policy: Ordered steps on consecutive failures: RETRY, STALL, REPAIR:<model>
        agent_notes: Short notes from repair agents about implementation details
    """
    body = {}
    if name is not None:
        body["name"] = name
    if target_url is not None:
        body["target_url"] = target_url
    if scraping_prompt is not None:
        body["scraping_prompt"] = scraping_prompt
    if cron_schedule is not None:
        body["cron_schedule"] = cron_schedule
    if repair_policy is not None:
        body["repair_policy"] = repair_policy
    if agent_notes is not None:
        body["agent_notes"] = agent_notes
    return _conductor("PATCH", f"/scrapers/{scraper_id}", body)


@mcp.tool()
def remove_scraper(scraper_id: str) -> dict:
    """Stop and remove a scraper from the fleet.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return _conductor("DELETE", f"/scrapers/{scraper_id}")


# ---------------------------------------------------------------------------
# Conductor: scraper operations
# ---------------------------------------------------------------------------

@mcp.tool()
def run_scraper(scraper_id: str) -> dict:
    """Manually trigger a single scraper run.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return _conductor("POST", f"/scrapers/{scraper_id}/run")


@mcp.tool()
def stop_scraper(scraper_id: str) -> dict:
    """Stop a running scraper and clean up debug/repair containers.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return _conductor("POST", f"/scrapers/{scraper_id}/stop")


@mcp.tool()
def launch_debug(scraper_id: str) -> dict:
    """Launch a scraper in debug mode with browser server kept alive.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return _conductor("POST", f"/scrapers/{scraper_id}/launch_debug")


@mcp.tool()
def repair_scraper(
    scraper_id: str,
    lazy: bool = True,
    sockpuppet: bool = False,
) -> dict:
    """Launch a dev-agent to repair a broken scraper.

    Args:
        scraper_id: e.g. 'scraper-001'
        lazy: Skip if last run succeeded (default True)
        sockpuppet: Start MCP server for interactive repair (default False)
    """
    return _conductor("POST", f"/scrapers/{scraper_id}/repair", {
        "lazy": lazy,
        "sockpuppet": sockpuppet,
    })


# ---------------------------------------------------------------------------
# Dev-agent: repair tools (forwarded to active repair containers)
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_scraper_info(scraper_id: str) -> dict:
    """Get full repair context: env vars, last error, current script.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return await _call_dev_agent(scraper_id, "get_scraper_info")


@mcp.tool()
async def browse_page(scraper_id: str, url: str, javascript: str = "") -> dict:
    """Browse a URL using the debug scraper's live browser.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: The scraper whose debug browser to use
        url: The URL to navigate to
        javascript: Optional JS to evaluate via page.evaluate()
    """
    return await _call_dev_agent(scraper_id, "browse_page", {"url": url, "javascript": javascript})


@mcp.tool()
async def test_selector(scraper_id: str, url: str, selector: str) -> dict:
    """Test a CSS selector against a page using the debug scraper's browser.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: The scraper whose debug browser to use
        url: The URL to navigate to
        selector: CSS selector to test
    """
    return await _call_dev_agent(scraper_id, "test_selector", {"url": url, "selector": selector})


@mcp.tool()
async def read_scraper_script(scraper_id: str) -> str:
    """Read the current scraper.py script.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    result = await _call_dev_agent(scraper_id, "read_scraper_script")
    if isinstance(result, dict) and "error" in result:
        return json.dumps(result)
    return result if isinstance(result, str) else json.dumps(result)


@mcp.tool()
async def write_scraper_script(scraper_id: str, content: str) -> str:
    """Write a new scraper.py script to replace the current one.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: e.g. 'scraper-001'
        content: The full Python script content
    """
    result = await _call_dev_agent(scraper_id, "write_scraper_script", {"content": content})
    return result if isinstance(result, str) else json.dumps(result)


@mcp.tool()
async def update_agent_notes(scraper_id: str, notes: str) -> str:
    """Update the agent_notes for a scraper via its active repair container.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: e.g. 'scraper-001'
        notes: Short paragraph about implementation details or past issues
    """
    result = await _call_dev_agent(scraper_id, "update_agent_notes", {"notes": notes})
    return result if isinstance(result, str) else json.dumps(result)


@mcp.tool()
async def test_scraper_script(scraper_id: str) -> dict:
    """Run the current scraper.py against the debug scraper's live browser.
    Requires an active repair container for this scraper.

    Args:
        scraper_id: e.g. 'scraper-001'
    """
    return await _call_dev_agent(scraper_id, "test_scraper_script")


# ---------------------------------------------------------------------------
# DB-Restful: content & events
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rss_content(
    scraper_id: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list:
    """Get scraped content from the database.

    Args:
        scraper_id: Filter to a single scraper (optional)
        limit: Max rows to return (default 100)
        offset: Pagination offset (default 0)
    """
    params = f"?limit={limit}&offset={offset}"
    if scraper_id:
        params += f"&scraper_id={scraper_id}"
    return _db_restful("GET", f"/rss_content{params}")


@mcp.tool()
def find_events(
    source: str = "",
    event_type: str = "",
    container_id: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list:
    """Query events from the event log.

    Args:
        source: Filter by source (e.g. 'conductor', 'dev-agent')
        event_type: Filter by type (e.g. 'scraper_run_completed', 'repair_launched')
        container_id: Filter by scraper ID
        limit: Max rows (default 100)
        offset: Pagination offset (default 0)
    """
    params = f"?limit={limit}&offset={offset}"
    if source:
        params += f"&source={source}"
    if event_type:
        params += f"&event_type={event_type}"
    if container_id:
        params += f"&container_id={container_id}"
    return _db_restful("GET", f"/find_events{params}")


if __name__ == "__main__":
    log.info("MCP proxy starting on 0.0.0.0:8080")
    mcp.run(transport="streamable-http")
