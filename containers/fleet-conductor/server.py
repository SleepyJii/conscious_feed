"""
Fleet Conductor API — manages a fleet of hybrid-scraper containers.

This module is the thin HTTP layer only. Orchestration logic lives in
fleet.py, filesystem state in state_helpers/, DB queries in api_helpers/.
"""

from __future__ import annotations

import logging
import subprocess
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import state_helpers as state
import api_helpers as api
import fleet
from config import FLEET_DATA, SCRAPER_IMAGE
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
    data = state.load()
    services = data.get("services", {})
    states = state.running_states()
    mon = api.get_monitoring_bulk(list(services.keys()))

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
    data = state.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    spec = ScraperSpec.from_compose_service(scraper_id, services[scraper_id])
    spec.monitoring = api.get_monitoring(scraper_id)
    states = state.running_states()
    d = spec.to_dict()
    d["container_state"] = states.get(scraper_id, "not running")
    return d

@app.post("/scrapers", status_code=201)
def add_scraper(body: ScraperAdd):
    """Deploy a new scraper to the fleet."""
    data = state.load()
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
    state.save(data)
    fleet.sync_crontab(data)
    fleet.init_scraper_dir(spec.scraper_id)

    result = state.run("up", "-d", spec.scraper_id)
    if result.returncode != 0:
        log.error("docker compose up failed for %s: %s", spec.scraper_id, result.stderr)
        raise HTTPException(500, f"docker compose up failed: {result.stderr}")

    api.emit("scraper_created", container_id=spec.scraper_id, payload=spec.user_params())
    log.info("Added scraper %s (%s)", spec.scraper_id, spec.target_url)
    return spec.to_dict()


@app.patch("/scrapers/{scraper_id}")
def edit_scraper(scraper_id: str, body: ScraperEdit):
    """Edit user-defined params on an existing scraper and recreate it."""
    data = state.load()
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
    state.save(data)
    fleet.sync_crontab(data)

    result = state.run("up", "-d", "--force-recreate", scraper_id)
    if result.returncode != 0:
        log.error("Recreate failed for %s: %s", scraper_id, result.stderr)
        raise HTTPException(500, f"Recreate failed: {result.stderr}")

    api.emit("scraper_modified", container_id=scraper_id, payload=spec.user_params())
    log.info("Edited scraper %s", scraper_id)
    return spec.to_dict()


@app.post("/scrapers/{scraper_id}/run")
def run_scraper(scraper_id: str):
    """Manually trigger a single scraper run (same as what cron does)."""
    data = state.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    log.info("Manual run triggered for %s", scraper_id)
    api.emit("scraper_launched", container_id=scraper_id, payload={"trigger": "manual"})
    result = state.run("run", "--rm", scraper_id, timeout=300)
    api.emit("scraper_run_completed", container_id=scraper_id, payload={
        "trigger": "manual",
        "exit_code": result.returncode,
    })

    return {
        "scraper_id": scraper_id,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@app.post("/scrapers/{scraper_id}/launch_debug")
def launch_debug(scraper_id: str):
    """Launch a scraper in debug mode — runs the script then keeps the
    container alive with the Playwright browser server still running.
    Use docker exec to connect to the browser via WS_ENDPOINT."""
    data = state.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    # Launch detached with DEBUG_MODE=1 so the container persists
    log.info("Debug launch for %s", scraper_id)
    result = state.run("run", "-d", "-e", "DEBUG_MODE=1", scraper_id)

    if result.returncode != 0:
        log.error("Debug launch failed for %s: %s", scraper_id, result.stderr)
        raise HTTPException(500, f"Debug launch failed: {result.stderr}")

    container_id = result.stdout.strip()

    # Wait for the browser server to be ready (writes config.json)
    for _ in range(30):
        time.sleep(0.5)
        if (FLEET_DATA / scraper_id / "browser.sock").exists():
            break

    api.emit("scraper_debug_launched", container_id=scraper_id, payload={
        "docker_container_id": container_id,
    })

    return {
        "scraper_id": scraper_id,
        "container_id": container_id,
        "status": "debug container running",
    }


@app.post("/scrapers/{scraper_id}/stop")
def stop_scraper(scraper_id: str):
    """Stop a running scraper and clean up debug containers if present."""
    data = state.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    stopped = []

    # Stop any running containers for this scraper (debug or normal)
    # docker compose rm handles the compose-managed container
    result = state.run("rm", "-fsv", scraper_id)
    if result.returncode == 0:
        stopped.append(scraper_id)

    # Also kill any orphaned debug run containers (docker compose run creates these)
    ps_result = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"name=fleet-data-{scraper_id}-run"],
        capture_output=True, text=True,
    )
    for cid in ps_result.stdout.strip().splitlines():
        if cid:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
            stopped.append(cid[:12])

    # Clean up stale socket file
    sock = FLEET_DATA / scraper_id / "browser.sock"
    if sock.exists():
        sock.unlink()

    log.info("Stopped %s: %s", scraper_id, stopped)
    return {
        "scraper_id": scraper_id,
        "stopped": stopped,
        "status": "stopped",
    }

@app.delete("/scrapers/{scraper_id}")
def remove_scraper(scraper_id: str):
    """Stop and remove a scraper from the fleet."""
    data = state.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    state.run("rm", "-fsv", scraper_id)

    del services[scraper_id]
    state.save(data)
    fleet.sync_crontab(data)

    api.emit("scraper_deleted", container_id=scraper_id)
    log.info("Removed scraper %s", scraper_id)
    return {"scraper_id": scraper_id, "status": "removed"}

@app.post("/batch-update")
def batch_update_scrapers(scraper_json : list[dict]):
    """
    Update multiple scrapers in a single request. Each dict needs to have the fields:
    - scraper_id (str)
    - name (str, optional)
    - target_url (str)
    - scraping_prompt (str)
    If the scraper id does not exist, it will be created. If it does exist,
    the existing scraper will be updated with the new values.
    """
    data = state.load()
    services = data.setdefault("services", {})

    updated_scrapers = []
    for scraper_data in scraper_json:
        scraper_id = scraper_data.get("scraper_id")
        if not scraper_id:
            continue

        existing_spec = None
        if scraper_id in services:
            existing_spec = ScraperSpec.from_compose_service(scraper_id, services[scraper_id])

        spec = ScraperSpec(
            scraper_id=scraper_id,
            name=scraper_data.get("name") or existing_spec.name if existing_spec else "",
            target_url=scraper_data.get("target_url") or existing_spec.target_url if existing_spec else "",
            scraping_prompt=scraper_data.get("scraping_prompt") or existing_spec.scraping_prompt if existing_spec else "",
            cron_schedule=scraper_data.get("cron_schedule") or existing_spec.cron_schedule if existing_spec else "",
        )

        services[spec.scraper_id] = spec.to_compose_service(SCRAPER_IMAGE)
        updated_scrapers.append(spec)

    state.save(data)
    fleet.sync_crontab(data)

    for spec in updated_scrapers:
        result = state.run("up", "-d", "--force-recreate", spec.scraper_id)
        if result.returncode != 0:
            log.error("Failed to update %s: %s", spec.scraper_id, result.stderr)

    return {"updated": [spec.to_dict() for spec in updated_scrapers]}