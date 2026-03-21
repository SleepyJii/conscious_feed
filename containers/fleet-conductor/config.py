"""
Shared configuration — paths, image names, database credentials.
"""

from pathlib import Path

# Fleet data volume (compose file, per-scraper scripts, shared state)
FLEET_DATA = Path("/fleet-data")
COMPOSE_FILE = FLEET_DATA / "docker-compose.yml"

# Docker image for scraper containers
SCRAPER_IMAGE = "conscious-feed/hybrid-scraper"

# Database credentials (internal Docker network only)
DB_HOST = "db"
DB_PORT = "5432"
DB_NAME = "scrape_db"
DB_USER = "conscious_feed"
DB_PASS = "conscious_feed"
