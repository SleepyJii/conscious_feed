"""
Dev-agent MCP server — exposes repair tools for Claude Code.

Connects to a debug hybrid-scraper's browser via WS_ENDPOINT to diagnose
and fix broken scraper scripts. Runs on 0.0.0.0:8080 inside the container.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("dev-agent", host="0.0.0.0", port=8080)

SCRAPER_ID = os.environ.get("SCRAPER_ID", "unknown")
TARGET_URL = os.environ.get("TARGET_URL", "")
SCRAPING_PROMPT = os.environ.get("SCRAPING_PROMPT", "")
SCRAPER_DIR = os.environ.get("SCRAPER_DIR", "")
WS_ENDPOINT = os.environ.get("WS_ENDPOINT", "")
AGENT_NOTES = os.environ.get("AGENT_NOTES", "")


@mcp.tool()
def get_scraper_info() -> dict:
    """Get full context for the repair: env vars, last error, current script."""
    info = {
        "scraper_id": SCRAPER_ID,
        "target_url": TARGET_URL,
        "scraping_prompt": SCRAPING_PROMPT,
        "scraper_dir": SCRAPER_DIR,
        "ws_endpoint": WS_ENDPOINT,
        "agent_notes": AGENT_NOTES,
    }

    error_file = Path(SCRAPER_DIR) / "last_error.txt"
    if error_file.exists():
        info["last_error"] = error_file.read_text().strip()
    else:
        info["last_error"] = ""

    script_file = Path(SCRAPER_DIR) / "scraper.py"
    if script_file.exists():
        info["scraper_script"] = script_file.read_text()
    else:
        info["scraper_script"] = ""

    return info


def _browse_page_sync(url: str, javascript: str = "") -> dict:
    from playwright.sync_api import sync_playwright

    result = {"url": url, "error": None}
    try:
        p = sync_playwright().start()
        browser = p.chromium.connect(WS_ENDPOINT)
        page = browser.new_context().new_page()
        page.goto(url, timeout=30000)

        result["title"] = page.title()
        result["final_url"] = page.url
        result["body_text"] = page.inner_text("body")[:10000]

        if javascript:
            result["js_result"] = str(page.evaluate(javascript))

        page.close()
        browser.close()
        p.stop()
    except Exception as e:
        result["error"] = str(e)

    return result


@mcp.tool()
async def browse_page(url: str, javascript: str = "") -> dict:
    """Browse a URL using the debug scraper's browser. Optionally run JavaScript.

    Args:
        url: The URL to navigate to
        javascript: Optional JS to evaluate via page.evaluate()
    """
    return await asyncio.to_thread(_browse_page_sync, url, javascript)


def _test_selector_sync(url: str, selector: str) -> dict:
    from playwright.sync_api import sync_playwright

    result = {"url": url, "selector": selector, "error": None}
    try:
        p = sync_playwright().start()
        browser = p.chromium.connect(WS_ENDPOINT)
        page = browser.new_context().new_page()
        page.goto(url, timeout=30000)

        elements = page.query_selector_all(selector)
        result["count"] = len(elements)

        matches = []
        for el in elements[:20]:
            match = {
                "tag": el.evaluate("el => el.tagName.toLowerCase()"),
                "text": (el.inner_text() or "").strip()[:200],
            }
            href = el.get_attribute("href")
            if href:
                match["href"] = href
            src = el.get_attribute("src")
            if src:
                match["src"] = src
            cls = el.get_attribute("class")
            if cls:
                match["class"] = cls
            matches.append(match)

        result["matches"] = matches

        page.close()
        browser.close()
        p.stop()
    except Exception as e:
        result["error"] = str(e)

    return result


@mcp.tool()
async def test_selector(url: str, selector: str) -> dict:
    """Test a CSS selector against a page using the debug scraper's browser.

    Args:
        url: The URL to navigate to
        selector: CSS selector to test (e.g. 'article h2', 'div.content p')
    """
    return await asyncio.to_thread(_test_selector_sync, url, selector)


@mcp.tool()
def read_scraper_script() -> str:
    """Read the current scraper.py script."""
    script_file = Path(SCRAPER_DIR) / "scraper.py"
    if script_file.exists():
        return script_file.read_text()
    return "(no scraper.py found)"


@mcp.tool()
def write_scraper_script(content: str) -> str:
    """Write a new scraper.py script to replace the current one.

    Args:
        content: The full Python script content to write
    """
    script_file = Path(SCRAPER_DIR) / "scraper.py"
    script_file.write_text(content)
    return f"Wrote {len(content)} bytes to {script_file}"


@mcp.tool()
async def test_scraper_script() -> dict:
    """Run the current scraper.py against the debug scraper's live browser.

    Executes the script as a subprocess with WS_ENDPOINT and TARGET_URL set,
    connecting to the same browser instance the production scraper uses.
    """
    script_file = Path(SCRAPER_DIR) / "scraper.py"
    if not script_file.exists():
        return {"error": "No scraper.py found", "exit_code": 1}

    env = os.environ.copy()
    env["WS_ENDPOINT"] = WS_ENDPOINT
    env["TARGET_URL"] = TARGET_URL

    def _run():
        try:
            result = subprocess.run(
                ["python3", str(script_file)],
                capture_output=True, text=True, timeout=60, env=env,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:5000],
            }
        except subprocess.TimeoutExpired:
            return {"error": "Script timed out after 60s", "exit_code": 1}

    return await asyncio.to_thread(_run)


@mcp.tool()
def update_agent_notes(notes: str) -> str:
    """Update the agent_notes field for this scraper on the conductor.

    Use this to leave short notes (a few sentences max) about implementation
    details, past issues, or why the script works the way it does. These notes
    persist across repair sessions so future agents have context.

    Args:
        notes: Short paragraph of notes about the scraper implementation
    """
    import urllib.request
    import urllib.error

    url = f"http://conductor:8000/scrapers/{SCRAPER_ID}"
    data = json.dumps({"agent_notes": notes}).encode()
    req = urllib.request.Request(url, data=data, method="PATCH")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return f"Updated agent_notes for {SCRAPER_ID}"
    except urllib.error.HTTPError as e:
        return f"Failed to update notes: HTTP {e.code}"
    except urllib.error.URLError as e:
        return f"Failed to reach conductor: {e.reason}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
