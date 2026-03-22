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

    # TODO: implement — see SCRAPING_PROMPT env var for what to extract
    raise NotImplementedError("Scraper not yet implemented")

if __name__ == "__main__":
    main()
"""


def next_scraper_id(services: dict) -> str:
    """Generate a unique random scraper ID (scraper-a1b2c3d4).

    Uses 8 hex characters. Checks against existing services and
    fleet-data directories to avoid collisions.
    """
    import secrets

    existing = set(services.keys())
    if FLEET_DATA.is_dir():
        existing.update(e.name for e in FLEET_DATA.iterdir() if e.is_dir())

    while True:
        candidate = f"scraper-{secrets.token_hex(4)}"
        if candidate not in existing:
            return candidate


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
