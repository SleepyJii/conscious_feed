"""
Fleet Conductor API — manages a fleet of hybrid-scraper containers
via a generated docker-compose file and the Docker CLI.
"""

import json
import subprocess
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from scraper_spec import ScraperSpec
from cron import update_crontab

app = FastAPI(title="Fleet Conductor")

COMPOSE_DIR = Path("/app/fleet")
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yml"
FLEET_SHARED = Path("/fleet-shared")
SCRAPER_IMAGE = "conscious-feed/hybrid-scraper"

STUB_SCRAPER = """\
import json
import os
from playwright.sync_api import sync_playwright

def main():
    ws = os.environ["WS_ENDPOINT"]
    url = os.environ.get("TARGET_URL", "")

    with sync_playwright() as p:
        browser = p.chromium.connect(ws)
        page = browser.new_context().new_page()
        page.goto(url)

        for el in page.query_selector_all("p"):
            text = el.inner_text().strip()
            if text:
                print(json.dumps({"url": page.url, "title": page.title(), "content": text}))

        page.close()

if __name__ == "__main__":
    main()
"""

# ---------------------------------------------------------------------------
# Compose helpers
# ---------------------------------------------------------------------------

def _load_compose() -> dict:
    if COMPOSE_FILE.exists():
        return yaml.safe_load(COMPOSE_FILE.read_text()) or {}
    return _compose_scaffold()


def _compose_scaffold() -> dict:
    """Blank fleet compose with the shared network declared."""
    return {
        "services": {},
        "networks": {
            "conscious-feed": {
                "external": True,
            },
        },
        "volumes": {
            "fleet-shared": {
                "external": True,
            },
        },
    }


def _save_compose(data: dict) -> None:
    COMPOSE_DIR.mkdir(parents=True, exist_ok=True)
    # Always ensure shared network + volume declarations are present
    data.setdefault("networks", {})["conscious-feed"] = {"external": True}
    data.setdefault("volumes", {})["fleet-shared"] = {"external": True}
    COMPOSE_FILE.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _compose_cmd(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _next_scraper_id(services: dict) -> str:
    """Generate the next incremental scraper ID (scraper-001, scraper-002, ...).

    Checks both current compose services and fleet-shared directories
    so IDs are never reused, even after removal.
    """
    max_n = 0
    # Check current compose services
    for key in services:
        if key.startswith("scraper-") and key[8:].isdigit():
            max_n = max(max_n, int(key[8:]))
    # Check fleet-shared for previously created (possibly removed) scrapers
    if FLEET_SHARED.is_dir():
        for entry in FLEET_SHARED.iterdir():
            if entry.is_dir() and entry.name.startswith("scraper-") and entry.name[8:].isdigit():
                max_n = max(max_n, int(entry.name[8:]))
    return f"scraper-{max_n + 1:03d}"


def _init_scraper_dir(scraper_id: str) -> None:
    """Create /fleet-shared/<scraper_id>/ with a stub scraper.py."""
    scraper_dir = FLEET_SHARED / scraper_id
    scraper_dir.mkdir(parents=True, exist_ok=True)
    script = scraper_dir / "scraper.py"
    if not script.exists():
        script.write_text(STUB_SCRAPER)



def _sync_crontab(compose: dict) -> None:
    """Rebuild and install the crontab from current compose state."""
    services = compose.get("services", {})
    specs = [
        ScraperSpec.from_compose_service(name, svc)
        for name, svc in services.items()
    ]
    update_crontab(specs, str(COMPOSE_FILE))


def _running_states() -> dict[str, str]:
    """Map service name -> container state from docker compose ps."""
    result = _compose_cmd("ps", "--format", "json")
    states: dict[str, str] = {}
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            try:
                entry = json.loads(line)
                states[entry.get("Service", "")] = entry.get("State", "unknown")
            except json.JSONDecodeError:
                pass
    return states


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScraperAdd(BaseModel):
    name: str = Field(default="", description="Human-readable name (defaults to the generated ID)")
    target_url: str = Field(description="URL the scraper should target")
    scraping_prompt: str = Field(description="Natural-language description of what to scrape")
    cron_schedule: str = Field(default="", description="Cron expression, e.g. '*/30 * * * *'")


class ScraperEdit(BaseModel):
    name: str | None = None
    target_url: str | None = None
    scraping_prompt: str | None = None
    cron_schedule: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scrapers", status_code=201)
def add_scraper(body: ScraperAdd):
    """Deploy a new scraper to the fleet."""
    compose = _load_compose()
    services = compose.setdefault("services", {})

    scraper_id = _next_scraper_id(services)

    spec = ScraperSpec(
        scraper_id=scraper_id,
        name=body.name,
        target_url=body.target_url,
        scraping_prompt=body.scraping_prompt,
        cron_schedule=body.cron_schedule,
    )
    services[spec.scraper_id] = spec.to_compose_service(SCRAPER_IMAGE)
    _save_compose(compose)
    _sync_crontab(compose)
    _init_scraper_dir(spec.scraper_id)

    result = _compose_cmd("up", "-d", spec.scraper_id)
    if result.returncode != 0:
        raise HTTPException(500, f"docker compose up failed: {result.stderr}")

    return spec.to_dict()


@app.patch("/scrapers/{scraper_id}")
def edit_scraper(scraper_id: str, body: ScraperEdit):
    """Edit user-defined params on an existing scraper and recreate it."""
    compose = _load_compose()
    services = compose.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    spec = ScraperSpec.from_compose_service(scraper_id, services[scraper_id])

    if body.name is not None:
        spec.name = body.name
    if body.target_url is not None:
        spec.target_url = body.target_url
    if body.scraping_prompt is not None:
        spec.scraping_prompt = body.scraping_prompt
    if body.cron_schedule is not None:
        spec.cron_schedule = body.cron_schedule

    services[scraper_id] = spec.to_compose_service(SCRAPER_IMAGE)
    _save_compose(compose)
    _sync_crontab(compose)

    result = _compose_cmd("up", "-d", "--force-recreate", scraper_id)
    if result.returncode != 0:
        raise HTTPException(500, f"Recreate failed: {result.stderr}")

    return spec.to_dict()


@app.delete("/scrapers/{scraper_id}")
def remove_scraper(scraper_id: str):
    """Stop and remove a scraper from the fleet."""
    compose = _load_compose()
    services = compose.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    _compose_cmd("rm", "-fsv", scraper_id)

    del services[scraper_id]
    _save_compose(compose)
    _sync_crontab(compose)

    return {"scraper_id": scraper_id, "status": "removed"}
