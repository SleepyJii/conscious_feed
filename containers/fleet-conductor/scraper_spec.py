"""
ScraperSpec — the user-facing representation of a scraper.

All docker-compose details are internal to the conductor. This dataclass
defines exactly what an API consumer sees and controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS

DEFAULT_REPAIR_POLICY = ["RETRY"]


def evaluate_repair_policy(policy: list[str], consecutive_failures: int) -> str:
    """Return the current policy action given consecutive failures.

    Policy is indexed by failure count: after failure N, use policy[N-1].
    The last element repeats forever after exhaustion.
    Returns "RETRY" if no failures or empty policy.
    """
    if consecutive_failures == 0 or not policy:
        return "RETRY"
    idx = min(consecutive_failures - 1, len(policy) - 1)
    return policy[idx]


@dataclass
class ScraperMonitoringSpec:
    """Live-calculated data about a running scraper. Never user-supplied."""

    health: str = "unknown"
    last_run: datetime | None = None
    total_runs: int = 0
    consecutive_failures: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["last_run"] is not None:
            d["last_run"] = d["last_run"].isoformat()
        return d


@dataclass
class ScraperSpec:
    """User-defined configuration for a scraper."""

    scraper_id: str
    target_url: str
    scraping_prompt: str
    name: str = ""
    cron_schedule: str = ""
    repair_policy: list[str] = field(default_factory=lambda: list(DEFAULT_REPAIR_POLICY))
    agent_notes: str = "SCRAPER NOT YET IMPLEMENTED"

    monitoring: ScraperMonitoringSpec | None = field(default=None, repr=False)

    def __post_init__(self):
        if not self.name:
            self.name = self.scraper_id

    def current_policy_action(self) -> str:
        """Evaluate repair_policy against current consecutive failures."""
        failures = self.monitoring.consecutive_failures if self.monitoring else 0
        return evaluate_repair_policy(self.repair_policy, failures)

    # ---- serialisation helpers ----

    def to_dict(self) -> dict:
        """Return a JSON-safe dict of all fields."""
        d = {
            "scraper_id": self.scraper_id,
            "name": self.name,
            "target_url": self.target_url,
            "scraping_prompt": self.scraping_prompt,
            "cron_schedule": self.cron_schedule,
            "repair_policy": self.repair_policy,
            "agent_notes": self.agent_notes,
        }
        if self.monitoring is not None:
            d["monitoring"] = self.monitoring.to_dict()
        return d

    def user_params(self) -> dict:
        """Only the fields a user supplies when creating/editing."""
        return {
            "name": self.name,
            "target_url": self.target_url,
            "scraping_prompt": self.scraping_prompt,
            "cron_schedule": self.cron_schedule,
            "repair_policy": self.repair_policy,
            "agent_notes": self.agent_notes,
        }

    # ---- compose translation ----

    def to_compose_service(self, image: str) -> dict:
        """Translate this spec into a docker-compose service definition."""
        env = {
            "SCRAPER_ID": self.scraper_id,
            "SCRAPER_NAME": self.name,
            "TARGET_URL": self.target_url,
            "SCRAPING_PROMPT": self.scraping_prompt,
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "DB_NAME": DB_NAME,
            "DB_USER": DB_USER,
            "DB_PASS": DB_PASS,
        }
        if self.cron_schedule:
            env["CRON_SCHEDULE"] = self.cron_schedule
        env["REPAIR_POLICY"] = ",".join(self.repair_policy)
        if self.agent_notes:
            env["AGENT_NOTES"] = self.agent_notes

        return {
            "image": image,
            "container_name": self.scraper_id,
            "restart": "no",
            "environment": env,
            "networks": ["conscious-feed"],
            "volumes": ["fleet-data:/fleet-data"],
        }

    @classmethod
    def from_compose_service(cls, scraper_id: str, svc: dict) -> ScraperSpec:
        """Reconstruct a ScraperSpec from a compose service definition."""
        env = svc.get("environment") or {}

        # Parse repair_policy from comma-separated env var
        raw_policy = env.get("REPAIR_POLICY", "")
        if raw_policy:
            repair_policy = [s.strip() for s in raw_policy.split(",") if s.strip()]
        else:
            # Backward compat: old AUTOREPAIR=1 → sensible repair policy
            if env.get("AUTOREPAIR", "") == "1":
                repair_policy = ["RETRY", "RETRY", "REPAIR:haiku", "STALL"]
            else:
                repair_policy = list(DEFAULT_REPAIR_POLICY)

        return cls(
            scraper_id=scraper_id,
            name=env.get("SCRAPER_NAME", ""),
            target_url=env.get("TARGET_URL", ""),
            scraping_prompt=env.get("SCRAPING_PROMPT", ""),
            cron_schedule=env.get("CRON_SCHEDULE", ""),
            repair_policy=repair_policy,
            agent_notes=env.get("AGENT_NOTES", "SCRAPER NOT YET IMPLEMENTED"),
        )
