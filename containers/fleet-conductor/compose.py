"""
Compose helpers — load/save the fleet docker-compose file and run Docker CLI commands.
"""

from __future__ import annotations

import json
import logging
import subprocess

import yaml

from config import FLEET_DATA, COMPOSE_FILE

log = logging.getLogger(__name__)


def scaffold() -> dict:
    """Blank fleet compose with the shared network and volume declared."""
    return {
        "services": {},
        "networks": {
            "conscious-feed": {"external": True},
        },
        "volumes": {
            "fleet-data": {"external": True},
        },
    }


def load() -> dict:
    """Load the fleet compose file, or return a fresh scaffold if missing."""
    if COMPOSE_FILE.exists():
        return yaml.safe_load(COMPOSE_FILE.read_text()) or {}
    return scaffold()


def save(data: dict) -> None:
    """Write the fleet compose file, ensuring shared infra declarations."""
    FLEET_DATA.mkdir(parents=True, exist_ok=True)
    data.setdefault("networks", {})["conscious-feed"] = {"external": True}
    data.setdefault("volumes", {})["fleet-data"] = {"external": True}
    COMPOSE_FILE.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False)
    )
    log.debug("Saved fleet compose to %s", COMPOSE_FILE)


def run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a docker compose command against the fleet compose file."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    log.debug("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def running_states() -> dict[str, str]:
    """Map service name → container state from docker compose ps."""
    result = run("ps", "--format", "json")
    states: dict[str, str] = {}
    if result.returncode != 0 or not result.stdout.strip():
        return states
    for line in result.stdout.strip().splitlines():
        try:
            entry = json.loads(line)
            states[entry.get("Service", "")] = entry.get("State", "unknown")
        except json.JSONDecodeError:
            pass
    return states
