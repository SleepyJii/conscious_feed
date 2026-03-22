---
name: repair-scraper
description: Launch a dev-agent for a broken scraper and use MCP tools to diagnose and fix the scraper script. Use when the user asks to fix or repair a specific scraper.
argument-hint: <scraper-id>
---

Repair a broken scraper using MCP tools. All interaction goes through the `conscious-feed-tools` MCP server — no curl or docker access needed.

## Target scraper: `$ARGUMENTS`

## Step 1: Gather context

Call `get_scraper` with scraper_id `$ARGUMENTS` to get config and health.

## Step 2: Launch repair dev-agent

Call `repair_scraper` with `scraper_id: "$ARGUMENTS"`, `lazy: false`, `sockpuppet: true`.

This launches a debug scraper (live browser) and a dev-agent (MCP server) connected to it. The dev-agent tools become available through the proxy.

## Step 3: Diagnose

Call `get_scraper_info` with `scraper_id: "$ARGUMENTS"` to get env vars, last error, and current script.

**Read the `scraping_prompt` carefully** — this is the user's intent. Your repaired script must faithfully implement what the user asked for.

Call `browse_page` with `scraper_id: "$ARGUMENTS"` and the target URL to explore the page. If the page doesn't load (DNS error, SSL error, 404), this is a **config problem** — note it for Step 7.

Call `test_selector` with `scraper_id: "$ARGUMENTS"` to test CSS selectors against the live page. Compare what the `scraping_prompt` asks for vs what the page actually contains.

## Step 4: Fix the scraper script

Call `write_scraper_script` with `scraper_id: "$ARGUMENTS"` and the corrected script content.

The script must:
- Read `WS_ENDPOINT` and `TARGET_URL` from env
- Connect to Playwright via `p.chromium.connect(ws)` (NOT `launch()`)
- Output JSON lines to stdout with fields: `url`, `title`, `content`, and `published_at` (ISO 8601 datetime if available on the page, otherwise omit)
- Not import or interact with the database

**The script must faithfully implement the user's `SCRAPING_PROMPT`.** Match the selectors and extraction logic to what the user actually asked for.

## Step 5: Test the fix

Call `test_scraper_script` with `scraper_id: "$ARGUMENTS"` to run the script against the live debug browser. Check that:
- exit_code is 0
- stdout contains valid JSONL
- stderr has no errors

If it fails, iterate: read the error, adjust the script, test again.

## Step 6: Clean up and verify

Call `stop_scraper` with `scraper_id: "$ARGUMENTS"` to stop repair containers.

Call `run_scraper` with `scraper_id: "$ARGUMENTS"` for a real end-to-end test.

## Step 7: Report config issues

If during diagnosis you found problems **not fixable by editing the scraper script**, report them clearly:

- **Bad URL**: target_url doesn't resolve, returns 404, or redirects unexpectedly
- **Prompt mismatch**: scraping_prompt asks for data that doesn't exist on the target page
- **Anti-bot blocking**: site blocks automated access
- **Authentication required**: page needs login credentials
