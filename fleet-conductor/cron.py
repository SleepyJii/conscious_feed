"""
Cron helpers — builds and installs a crontab from ScraperSpec list.

Each scraper with a cron_schedule gets a line that triggers
`docker compose run --rm` against the fleet compose file, so the
container's crond handles all scheduling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scraper_spec import ScraperSpec

CRONTAB_PATH = Path("/app/fleet/crontab")


def build_crontab(specs: list[ScraperSpec], compose_file: str) -> str:
    """Generate crontab contents from a list of ScraperSpecs.

    Only specs with a non-empty cron_schedule are included.
    Returns the full crontab file as a string.
    """
    lines: list[str] = []
    for spec in specs:
        if not spec.cron_schedule:
            continue
        cmd = f"docker compose -f {compose_file} run --rm {spec.scraper_id}"
        lines.append(f"{spec.cron_schedule} {cmd}")

    # crontab files must end with a newline
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def install_crontab(content: str) -> None:
    """Write the crontab file and load it into crond."""
    CRONTAB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRONTAB_PATH.write_text(content)

    if content.strip():
        subprocess.run(["crontab", str(CRONTAB_PATH)], check=True)
    else:
        # No scheduled scrapers — clear the crontab
        subprocess.run(["crontab", "-r"], capture_output=True)


def update_crontab(specs: list[ScraperSpec], compose_file: str) -> None:
    """One-shot: rebuild and install the crontab from current specs."""
    content = build_crontab(specs, compose_file)
    install_crontab(content)
