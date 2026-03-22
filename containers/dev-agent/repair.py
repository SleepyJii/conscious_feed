"""
Autonomous scraper repair agent — uses Claude Agent SDK with MCP tools.

Connects to the local dev-agent MCP server (localhost:8080) which provides
browser access and scraper script management. Diagnoses the failure,
fixes the script, validates the fix, then exits.
"""

import asyncio
import json
import os
import sys

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, SystemMessage

SCRAPER_ID = os.environ.get("SCRAPER_ID", "unknown")
TARGET_URL = os.environ.get("TARGET_URL", "")
SCRAPING_PROMPT = os.environ.get("SCRAPING_PROMPT", "")
SCRAPER_DIR = os.environ.get("SCRAPER_DIR", "")
MCP_URL = os.environ.get("MCP_URL", "http://localhost:8080/mcp")

def _resolve_model() -> str | None:
    """Resolve REPAIR_MODEL alias to a full Anthropic model ID.

    REPAIR_MODEL is set by the conductor at container launch (e.g. "haiku").
    MODEL_ALIASES is baked into the image at build time as a JSON string
    (e.g. '{"haiku":"claude-haiku-4-5-20251001","sonnet":"claude-sonnet-4-6"}').
    If the alias isn't found, the raw value is used as-is (allows full model IDs).
    Returns None if REPAIR_MODEL is not set (use SDK default).
    """
    raw = os.environ.get("REPAIR_MODEL", "")
    if not raw:
        return None
    try:
        aliases = json.loads(os.environ.get("MODEL_ALIASES", "{}"))
    except json.JSONDecodeError:
        aliases = {}
    return aliases.get(raw, raw)

REPAIR_MODEL = _resolve_model()

SYSTEM_PROMPT = """\
You are an autonomous scraper repair agent running inside a Docker container.
You have MCP tools to diagnose and fix broken web scrapers.

## Your tools

- get_scraper_info() — returns env vars, last error, current scraper.py, and agent_notes from previous repairs
- browse_page(url, javascript?) — visit a URL via the debug browser
- test_selector(url, selector) — test CSS selectors against a live page
- read_scraper_script() — read the current scraper.py
- write_scraper_script(content) — write a new scraper.py
- test_scraper_script() — run the script against the live debug browser
- update_agent_notes(notes) — save short notes about your implementation for future agents

## Scraper script contract

Scripts you write must:
- Read WS_ENDPOINT and TARGET_URL from env
- Connect to Playwright via p.chromium.connect(ws) (NOT launch())
- Output JSON lines to stdout (one per item) with fields: "url", "title", "content", and "published_at" (ISO 8601 datetime if available on the page, otherwise omit)
- Not interact with the database — ingest.sh handles that downstream

## Your procedure

1. Call get_scraper_info() to understand the problem
2. Read the SCRAPING_PROMPT carefully — it describes what the user wants extracted
3. Call browse_page() with the target URL to see the page structure
4. Use test_selector() to find working CSS selectors
5. Write a fixed script with write_scraper_script()
6. Validate with test_scraper_script() — check exit_code=0 and stdout has JSONL
7. If the test fails, iterate: read the error, adjust, test again

## Config issues

If the target URL doesn't load (DNS, SSL, 404) or the page doesn't contain
what the SCRAPING_PROMPT asks for, that's a config problem you can't fix.
Write a clear explanation to the file {scraper_dir}/needs_attention.txt
describing the issue, and exit.

Keep your fixes minimal and focused. Don't over-engineer.

After completing a repair, always call update_agent_notes() with a brief summary
of what you found, what you changed, and any quirks about the target site.
This helps future repair agents understand context quickly.

## Giving up

If you determine the task is impossible or impractical (e.g. the site requires
authentication, blocks all automation, the scraping prompt asks for data that
doesn't exist on the page, or the site is too dynamic to scrape reliably),
you should:
1. Call update_agent_notes() explaining WHY you're giving up
2. Write "GIVE_UP" as the first line of your final response

Do NOT write a fake script that pretends to work. It's better to give up
honestly so the repair policy can advance and a human can review your notes.
""".format(scraper_dir=SCRAPER_DIR)

REPAIR_PROMPT = f"""\
Repair the scraper for: {SCRAPER_ID}

Target URL: {TARGET_URL}
User's scraping prompt: "{SCRAPING_PROMPT}"
Scraper directory: {SCRAPER_DIR}

Start by calling get_scraper_info() to see the current state and error.\
"""


async def repair():
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="acceptEdits",
        mcp_servers={
            "dev-agent": {
                "type": "http",
                "url": MCP_URL,
            }
        },
        allowed_tools=["mcp__dev-agent__*"],
        max_turns=20,
        **({"model": REPAIR_MODEL} if REPAIR_MODEL else {}),
    )

    # Returns: 0 = success, 1 = failure, 2 = gave up
    exit_code = 1
    try:
        async with asyncio.timeout(600):
            async for message in query(prompt=REPAIR_PROMPT, options=options):
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    mcp_servers = message.data.get("mcp_servers", [])
                    failed = [s for s in mcp_servers if s.get("status") != "connected"]
                    if failed:
                        print(f"repair: MCP connection failed: {failed}", file=sys.stderr)
                        return 1

                if isinstance(message, ResultMessage):
                    result_text = str(message.result) if message.result else ""
                    if result_text.strip().startswith("GIVE_UP"):
                        print(f"repair: agent gave up for {SCRAPER_ID}", file=sys.stderr)
                        exit_code = 2
                    elif message.subtype == "success":
                        print(f"repair: completed successfully for {SCRAPER_ID}")
                        exit_code = 0
                    else:
                        print(f"repair: failed for {SCRAPER_ID}: {result_text}", file=sys.stderr)
                        exit_code = 1

    except asyncio.TimeoutError:
        print(f"repair: timed out after 10 minutes for {SCRAPER_ID}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"repair: error for {SCRAPER_ID}: {e}", file=sys.stderr)
        return 1

    return exit_code


async def main():
    print(f"repair: starting autonomous repair for {SCRAPER_ID}")
    print(f"repair: target_url={TARGET_URL}")
    print(f"repair: scraping_prompt={SCRAPING_PROMPT}")

    exit_code = await repair()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
