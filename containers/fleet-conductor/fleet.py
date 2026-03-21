"""
Fleet orchestration — the glue between compose, cron, and the filesystem.

Handles scraper ID generation, per-scraper directory setup, stub script
creation, and crontab synchronisation.
"""

from __future__ import annotations

import logging

import state_helpers as state
from config import COMPOSE_FILE, FLEET_DATA, REPAIR_CRON_SCHEDULE
from scraper_spec import ScraperSpec

log = logging.getLogger(__name__)

STUB_SCRAPER = """\
import json
import os
from playwright.sync_api import sync_playwright

def main():
    ws = os.environ["WS_ENDPOINT"]
    url = os.environ.get("TARGET_URL", "")

    with sync_playwright() as p:
        browser = p.chromium.connect(ws)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")

        for el in page.query_selector_all("p"):
            text = el.inner_text().strip()
            if text:
                print(json.dumps({"url": page.url, "title": page.title(), "content": text}))

        page.close()

if __name__ == "__main__":
    main()
"""


def next_scraper_id(services: dict) -> str:
    """Generate the next incremental scraper ID (scraper-001, scraper-002, ...).

    Checks both current compose services and fleet-data directories
    so IDs are never reused, even after removal.
    """
    max_n = 0
    for key in services:
        if key.startswith("scraper-") and key[8:].isdigit():
            max_n = max(max_n, int(key[8:]))
    if FLEET_DATA.is_dir():
        for entry in FLEET_DATA.iterdir():
            if entry.is_dir() and entry.name.startswith("scraper-") and entry.name[8:].isdigit():
                max_n = max(max_n, int(entry.name[8:]))
    return f"scraper-{max_n + 1:03d}"


def init_scraper_dir(scraper_id: str) -> None:
    """Create /fleet-data/<scraper_id>/ with a stub scraper.py."""
    scraper_dir = FLEET_DATA / scraper_id
    scraper_dir.mkdir(parents=True, exist_ok=True)
    script = scraper_dir / "scraper.py"
    if not script.exists():
        script.write_text(STUB_SCRAPER)
        log.info("Wrote stub scraper to %s", script)


def sync_crontab(compose_data: dict) -> None:
    """Rebuild and install the crontab from current compose state."""
    services = compose_data.get("services", {})
    specs = [
        ScraperSpec.from_compose_service(name, svc)
        for name, svc in services.items()
    ]
    extra = [f"{REPAIR_CRON_SCHEDULE} /app/launch-repairs.sh"]
    state.update_crontab(specs, str(COMPOSE_FILE), extra_lines=extra)
    log.info("Crontab synced (%d scraper(s))", len(specs))
