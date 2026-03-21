"""
ScraperSpec — the user-facing representation of a scraper.

All docker-compose details are internal to the conductor. This dataclass
defines exactly what an API consumer sees and controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS


@dataclass
class ScraperMonitoringSpec:
    """Live-calculated data about a running scraper. Never user-supplied."""

    health: str = "unknown"
    last_run: datetime | None = None
    total_runs: int = 0

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

    monitoring: ScraperMonitoringSpec | None = field(default=None, repr=False)

    def __post_init__(self):
        if not self.name:
            self.name = self.scraper_id

    # ---- serialisation helpers ----

    def to_dict(self) -> dict:
        """Return a JSON-safe dict of all fields."""
        d = {
            "scraper_id": self.scraper_id,
            "name": self.name,
            "target_url": self.target_url,
            "scraping_prompt": self.scraping_prompt,
            "cron_schedule": self.cron_schedule,
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

        return {
            "image": image,
            "container_name": self.scraper_id,
            "restart": "unless-stopped",
            "environment": env,
            "networks": ["conscious-feed"],
            "volumes": ["fleet-shared:/fleet-shared"],
        }

    @classmethod
    def from_compose_service(cls, scraper_id: str, svc: dict) -> ScraperSpec:
        """Reconstruct a ScraperSpec from a compose service definition."""
        env = svc.get("environment") or {}
        return cls(
            scraper_id=scraper_id,
            name=env.get("SCRAPER_NAME", ""),
            target_url=env.get("TARGET_URL", ""),
            scraping_prompt=env.get("SCRAPING_PROMPT", ""),
            cron_schedule=env.get("CRON_SCHEDULE", ""),
        )
