"""
Fleet Conductor API — manages a fleet of hybrid-scraper containers.

This module is the thin HTTP layer only. Orchestration logic lives in
fleet.py, filesystem state in state_helpers/, DB queries in api_helpers/.
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import state_helpers as state
import api_helpers as api
import fleet
from config import FLEET_DATA, SCRAPER_IMAGE, DEV_AGENT_IMAGE
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
    autorepair: bool = Field(default=False, description="Auto-trigger repair on failure")


class ScraperEdit(BaseModel):
    name: str | None = None
    target_url: str | None = None
    scraping_prompt: str | None = None
    cron_schedule: str | None = None
    autorepair: bool | None = None


class RepairRequest(BaseModel):
    lazy: bool = Field(default=True, description="Skip if last run succeeded")
    sockpuppet: bool = Field(default=False, description="Keep container alive for external agent exec")


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


@app.get("/scrapers/repair-candidates")
def list_repair_candidates():
    """Return scraper IDs with autorepair=True that are currently failing."""
    data = state.load()
    services = data.get("services", {})

    candidates = []
    for name, svc in services.items():
        spec = ScraperSpec.from_compose_service(name, svc)
        if not spec.autorepair:
            continue
        mon = api.get_monitoring(name)
        if mon.health in ("failing", "degraded"):
            candidates.append(name)

    return {"candidates": candidates}


@app.get("/repair-containers")
def list_repair_containers():
    """List active repair containers with their MCP connection info."""
    ps_result = subprocess.run(
        ["docker", "ps", "--filter", "name=repair-scraper-",
         "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True, text=True,
    )
    containers = []
    for line in ps_result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        name = parts[0]
        status = parts[1] if len(parts) > 1 else ""
        ports = parts[2] if len(parts) > 2 else ""
        scraper_id = name.replace("repair-", "")
        mcp_port = None
        if "->8080" in ports:
            mcp_port = int(ports.split("->")[0].split(":")[-1])
        containers.append({
            "scraper_id": scraper_id,
            "container_name": name,
            "status": status,
            "mcp_port": mcp_port,
            "mcp_url": f"http://localhost:{mcp_port}" if mcp_port else None,
        })
    return {"repair_containers": containers}


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
        autorepair=body.autorepair,
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
    if body.autorepair is not None:
        spec.autorepair = body.autorepair

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
    result = subprocess.run(
        ["/app/run_wrapper.sh", str(FLEET_DATA / "docker-compose.yml"), scraper_id],
        capture_output=True, text=True, timeout=300,
    )

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

    # Stop repair container if running (managed via fleet compose)
    repair_service = f"repair-{scraper_id}"
    if repair_service in services:
        repair_result = state.run("rm", "-fsv", repair_service)
        if repair_result.returncode == 0:
            stopped.append(repair_service)
        del services[repair_service]
        state.save(data)
        fleet.sync_crontab(data)

    # Stop any running containers for this scraper (debug or normal)
    # docker compose rm handles the compose-managed container
    result = state.run("rm", "-fsv", scraper_id)
    if result.returncode == 0:
        stopped.append(scraper_id)

    # Also kill any orphaned run containers (docker compose run creates these)
    for name_filter in [f"fleet-{scraper_id}-run", f"fleet-repair-{scraper_id}-run"]:
        ps_result = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"name={name_filter}"],
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

def _get_debug_ws_endpoint(container_id: str) -> str:
    """Get the debug scraper's WS_ENDPOINT rewritten with its network IP."""
    ip_result = subprocess.run(
        ["docker", "inspect", "-f",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
         container_id],
        capture_output=True, text=True,
    )
    container_ip = ip_result.stdout.strip()

    config_result = subprocess.run(
        ["docker", "exec", container_id, "cat", "/app/playwright-server/config.json"],
        capture_output=True, text=True,
    )
    config = json.loads(config_result.stdout)
    ws = config["ws_endpoint"]  # ws://0.0.0.0:{port}/{hash}
    return ws.replace("0.0.0.0", container_ip)


@app.post("/scrapers/{scraper_id}/repair")
def repair_scraper(scraper_id: str, body: RepairRequest = RepairRequest()):
    """Launch a dev-agent to repair a broken scraper.

    In sockpuppet mode, also launches a debug scraper with a live browser,
    then starts the dev-agent as an MCP server connected to that browser.
    """
    data = state.load()
    services = data.get("services", {})

    if scraper_id not in services:
        raise HTTPException(404, f"Scraper '{scraper_id}' not found")

    spec = ScraperSpec.from_compose_service(scraper_id, services[scraper_id])

    if body.lazy:
        mon = api.get_monitoring(scraper_id)
        if mon.health == "healthy":
            api.emit("repair_skipped", container_id=scraper_id, payload={
                "reason": "last run succeeded",
            })
            return {"scraper_id": scraper_id, "status": "skipped", "reason": "last run succeeded"}

    # Skip if a repair service is already defined (running or exited)
    repair_service_name = f"repair-{scraper_id}"
    if repair_service_name in services:
        return {"scraper_id": scraper_id, "status": "skipped", "reason": "repair already running"}

    # Write last error to file for the dev-agent to read
    api.get_last_error(scraper_id)

    # Launch debug scraper to get a live browser
    log.info("Launching debug scraper for repair of %s", scraper_id)
    debug_result = state.run("run", "-d", "-e", "DEBUG_MODE=1", scraper_id)
    if debug_result.returncode != 0:
        log.error("Debug launch failed for %s: %s", scraper_id, debug_result.stderr)
        raise HTTPException(500, f"Debug launch failed: {debug_result.stderr}")

    debug_container_id = debug_result.stdout.strip()

    # Wait for browser server config.json to appear inside the container
    ws_endpoint = None
    for _ in range(30):
        time.sleep(1)
        try:
            ws_endpoint = _get_debug_ws_endpoint(debug_container_id)
            break
        except (json.JSONDecodeError, KeyError):
            continue

    if ws_endpoint is None:
        subprocess.run(["docker", "rm", "-f", debug_container_id], capture_output=True)
        raise HTTPException(500, "Debug browser failed to start — config.json never appeared")
    log.info("Debug browser for %s at %s", scraper_id, ws_endpoint)

    # Add dev-agent as a service in the fleet compose so it's managed by
    # docker compose -p fleet (and cleaned up with `down`)
    repair_service_name = f"repair-{scraper_id}"
    repair_env = {
        "SCRAPER_ID": spec.scraper_id,
        "TARGET_URL": spec.target_url,
        "SCRAPING_PROMPT": spec.scraping_prompt,
        "SCRAPER_DIR": f"/fleet-data/{spec.scraper_id}",
        "WS_ENDPOINT": ws_endpoint,
    }
    if body.sockpuppet:
        repair_env["SOCKPUPPET"] = "1"

    services[repair_service_name] = {
        "image": DEV_AGENT_IMAGE,
        "container_name": repair_service_name,
        "hostname": repair_service_name,
        "environment": repair_env,
        "networks": {"conscious-feed": {"aliases": [repair_service_name]}},
        "volumes": ["fleet-data:/fleet-data"],
    }
    state.save(data)

    result = state.run("run", "-d", repair_service_name)

    if result.returncode != 0:
        log.error("Repair launch failed for %s: %s", scraper_id, result.stderr)
        # Clean up the service definition
        del services[repair_service_name]
        state.save(data)
        subprocess.run(["docker", "rm", "-f", debug_container_id], capture_output=True)
        raise HTTPException(500, f"Repair launch failed: {result.stderr}")

    container_id = result.stdout.strip()

    # Wait for dev-agent MCP server readiness in sockpuppet mode
    if body.sockpuppet:
        for _ in range(30):
            time.sleep(0.5)
            try:
                s = socket.create_connection((f"repair-{scraper_id}", 8080), timeout=1)
                s.close()
                break
            except (ConnectionRefusedError, OSError):
                continue

    api.emit("repair_launched", container_id=scraper_id, payload={
        "docker_container_id": container_id,
        "debug_container_id": debug_container_id,
        "sockpuppet": body.sockpuppet,
        "lazy": body.lazy,
    })

    log.info("Repair launched for %s (sockpuppet=%s)", scraper_id, body.sockpuppet)
    response = {
        "scraper_id": scraper_id,
        "container_id": container_id,
        "debug_container_id": debug_container_id,
        "status": "repair launched",
        "sockpuppet": body.sockpuppet,
    }
    return response


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

        autorepair = scraper_data.get("autorepair")
        if autorepair is None and existing_spec:
            autorepair = existing_spec.autorepair
        spec = ScraperSpec(
            scraper_id=scraper_id,
            name=scraper_data.get("name") or existing_spec.name if existing_spec else "",
            target_url=scraper_data.get("target_url") or existing_spec.target_url if existing_spec else "",
            scraping_prompt=scraper_data.get("scraping_prompt") or existing_spec.scraping_prompt if existing_spec else "",
            cron_schedule=scraper_data.get("cron_schedule") or existing_spec.cron_schedule if existing_spec else "",
            autorepair=bool(autorepair),
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
