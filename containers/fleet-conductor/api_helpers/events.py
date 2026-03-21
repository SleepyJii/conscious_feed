"""
Event emitter — posts events to the db-restful service.
"""

from __future__ import annotations

import json
import logging
from urllib.request import urlopen, Request
from urllib.error import URLError

log = logging.getLogger(__name__)

DB_RESTFUL_URL = "http://restful_db:5000"


def emit(event_type: str, source: str = "conductor", container_id: str | None = None, payload: dict | None = None) -> None:
    """Fire-and-forget event registration via db-restful."""
    body = {
        "source": source,
        "event_type": event_type,
    }
    if container_id:
        body["container_id"] = container_id
    if payload:
        body["event_payload"] = payload

    try:
        req = Request(
            f"{DB_RESTFUL_URL}/register_event",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlopen(req, timeout=5)
        log.debug("Emitted event: %s %s", event_type, container_id or "")
    except (URLError, OSError) as e:
        log.warning("Failed to emit event %s: %s", event_type, e)
