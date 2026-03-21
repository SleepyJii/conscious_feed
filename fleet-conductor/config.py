"""
Shared configuration — paths, image names, database credentials.
"""

from pathlib import Path

# Compose management
COMPOSE_DIR = Path("/app/fleet")
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yml"

# Fleet shared volume (conductor writes scraper scripts, scrapers read them)
FLEET_SHARED = Path("/fleet-shared")

# Docker image for scraper containers
SCRAPER_IMAGE = "conscious-feed/hybrid-scraper"

# Database credentials (internal Docker network only)
DB_HOST = "db"
DB_PORT = "5432"
DB_NAME = "scrape_db"
DB_USER = "conscious_feed"
DB_PASS = "conscious_feed"
