"""
Shared configuration — paths, image names, database credentials.
"""

import os
from pathlib import Path

# Fleet data volume (compose file, per-scraper scripts, shared state)
FLEET_DATA = Path("/fleet-data")
COMPOSE_FILE = FLEET_DATA / "docker-compose.yml"
FLEET_PROJECT_NAME = "fleet"

# Docker images
SCRAPER_IMAGE = "conscious-feed/hybrid-scraper"
DEV_AGENT_IMAGE = "conscious-feed/dev-agent"

# Repair orchestration
REPAIR_CRON_SCHEDULE = os.environ.get("REPAIR_CRON_SCHEDULE", "0 */6 * * *")
MAX_CONCURRENT_REPAIRS = int(os.environ.get("MAX_CONCURRENT_REPAIRS", "2"))
MCP_HOST_PORT = 9200

# Database credentials (internal Docker network only)
DB_HOST = "db"
DB_PORT = "5432"
DB_NAME = "scrape_db"
DB_USER = "conscious_feed"
DB_PASS = "conscious_feed"
