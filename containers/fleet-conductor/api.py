"""
Fleet Conductor API — manages a fleet of hybrid-scraper containers.

This module is the thin HTTP layer only. Orchestration logic lives in
fleet.py, compose management in compose.py, config in config.py.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import compose
import fleet
import monitoring
from config import SCRAPER_IMAGE
from scraper_spec import ScraperSpec

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(title="Fleet Conductor")


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


@app.get("/scrapers")
def list_scrapers():
    """Return all scrapers with live container state and monitoring data."""
    data = compose.load()
    services = data.get("services", {})
    states = compose.running_states()
    mon = monitoring.get_monitoring_bulk(list(services.keys()))

    results = []
    for name, svc in services.items():
        spec = ScraperSpec.from_compose_service(name, svc)
        spec.monitoring = mon.get(name)
        d = spec.to_dict()
        d["container_state"] = states.get(name, "not running")
        results.append(d)

    return results


@app.get("/scrapers/{scraper_id}")
def get_scraper(scraper_id: str):
    """Return a single scraper's config and container state."""
    data = compose.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    spec = ScraperSpec.from_compose_service(scraper_id, services[scraper_id])
    spec.monitoring = monitoring.get_monitoring(scraper_id)
    states = compose.running_states()
    d = spec.to_dict()
    d["container_state"] = states.get(scraper_id, "not running")
    return d


@app.post("/scrapers", status_code=201)
def add_scraper(body: ScraperAdd):
    """Deploy a new scraper to the fleet."""
    data = compose.load()
    services = data.setdefault("services", {})

    scraper_id = fleet.next_scraper_id(services)
    spec = ScraperSpec(
        scraper_id=scraper_id,
        name=body.name,
        target_url=body.target_url,
        scraping_prompt=body.scraping_prompt,
        cron_schedule=body.cron_schedule,
    )

    services[spec.scraper_id] = spec.to_compose_service(SCRAPER_IMAGE)
    compose.save(data)
    fleet.sync_crontab(data)
    fleet.init_scraper_dir(spec.scraper_id)

    result = compose.run("up", "-d", spec.scraper_id)
    if result.returncode != 0:
        log.error("docker compose up failed for %s: %s", spec.scraper_id, result.stderr)
        raise HTTPException(500, f"docker compose up failed: {result.stderr}")

    log.info("Added scraper %s (%s)", spec.scraper_id, spec.target_url)
    return spec.to_dict()


@app.patch("/scrapers/{scraper_id}")
def edit_scraper(scraper_id: str, body: ScraperEdit):
    """Edit user-defined params on an existing scraper and recreate it."""
    data = compose.load()
    services = data.get("services", {})

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
    compose.save(data)
    fleet.sync_crontab(data)

    result = compose.run("up", "-d", "--force-recreate", scraper_id)
    if result.returncode != 0:
        log.error("Recreate failed for %s: %s", scraper_id, result.stderr)
        raise HTTPException(500, f"Recreate failed: {result.stderr}")

    log.info("Edited scraper %s", scraper_id)
    return spec.to_dict()


@app.post("/scrapers/{scraper_id}/run")
def run_scraper(scraper_id: str):
    """Manually trigger a single scraper run (same as what cron does)."""
    data = compose.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    log.info("Manual run triggered for %s", scraper_id)
    result = compose.run("run", "--rm", scraper_id, timeout=300)

    return {
        "scraper_id": scraper_id,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@app.delete("/scrapers/{scraper_id}")
def remove_scraper(scraper_id: str):
    """Stop and remove a scraper from the fleet."""
    data = compose.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    compose.run("rm", "-fsv", scraper_id)

    del services[scraper_id]
    compose.save(data)
    fleet.sync_crontab(data)

    log.info("Removed scraper %s", scraper_id)
    return {"scraper_id": scraper_id, "status": "removed"}
