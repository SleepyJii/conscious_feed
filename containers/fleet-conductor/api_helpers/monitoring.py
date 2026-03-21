"""
Monitoring queries — reads scraper_runs to build ScraperMonitoringSpec.
"""

from __future__ import annotations

import logging

import psycopg2

from pathlib import Path

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS, FLEET_DATA
from scraper_spec import ScraperMonitoringSpec

log = logging.getLogger(__name__)


def _connect():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS,
    )


def get_monitoring(scraper_id: str) -> ScraperMonitoringSpec:
    """Build monitoring spec for a single scraper from its run history."""
    try:
        conn = _connect()
        cur = conn.cursor()

        cur.execute(
            """SELECT count(*),
                      max(started_at),
                      (SELECT exit_code FROM scraper_runs
                       WHERE scraper_id = %s ORDER BY started_at DESC LIMIT 1)
               FROM scraper_runs WHERE scraper_id = %s""",
            (scraper_id, scraper_id),
        )
        total_runs, last_run, last_exit_code = cur.fetchone()

        # Consecutive failures: count recent runs with non-zero exit
        cur.execute(
            """SELECT exit_code FROM scraper_runs
               WHERE scraper_id = %s ORDER BY started_at DESC LIMIT 10""",
            (scraper_id,),
        )
        recent_codes = [r[0] for r in cur.fetchall()]

        conn.close()
    except Exception as e:
        log.warning("Failed to query scraper_runs: %s", e)
        return ScraperMonitoringSpec()

    if total_runs == 0:
        return ScraperMonitoringSpec(health="pending", total_runs=0)

    consecutive_failures = 0
    for code in recent_codes:
        if code != 0:
            consecutive_failures += 1
        else:
            break

    if last_exit_code == 0:
        health = "healthy"
    elif consecutive_failures >= 3:
        health = "failing"
    else:
        health = "degraded"

    return ScraperMonitoringSpec(
        health=health,
        last_run=last_run,
        total_runs=total_runs,
    )


def get_monitoring_bulk(scraper_ids: list[str]) -> dict[str, ScraperMonitoringSpec]:
    """Build monitoring specs for multiple scrapers in one DB round-trip."""
    if not scraper_ids:
        return {}

    try:
        conn = _connect()
        cur = conn.cursor()

        # Get totals and last run per scraper
        cur.execute(
            """SELECT scraper_id, count(*), max(started_at)
               FROM scraper_runs
               WHERE scraper_id = ANY(%s)
               GROUP BY scraper_id""",
            (scraper_ids,),
        )
        stats = {r[0]: {"total": r[1], "last_run": r[2]} for r in cur.fetchall()}

        # Get last 10 exit codes per scraper for health calculation
        cur.execute(
            """SELECT scraper_id, exit_code FROM (
                   SELECT scraper_id, exit_code,
                          row_number() OVER (PARTITION BY scraper_id ORDER BY started_at DESC) AS rn
                   FROM scraper_runs WHERE scraper_id = ANY(%s)
               ) sub WHERE rn <= 10""",
            (scraper_ids,),
        )
        recent: dict[str, list[int]] = {}
        for scraper_id, exit_code in cur.fetchall():
            recent.setdefault(scraper_id, []).append(exit_code)

        conn.close()
    except Exception as e:
        log.warning("Failed to query scraper_runs: %s", e)
        return {sid: ScraperMonitoringSpec() for sid in scraper_ids}

    result = {}
    for sid in scraper_ids:
        if sid not in stats:
            result[sid] = ScraperMonitoringSpec(health="pending", total_runs=0)
            continue

        codes = recent.get(sid, [])
        consecutive_failures = 0
        for code in codes:
            if code != 0:
                consecutive_failures += 1
            else:
                break

        last_exit = codes[0] if codes else None
        if last_exit == 0:
            health = "healthy"
        elif consecutive_failures >= 3:
            health = "failing"
        else:
            health = "degraded"

        result[sid] = ScraperMonitoringSpec(
            health=health,
            last_run=stats[sid]["last_run"],
            total_runs=stats[sid]["total"],
        )

    return result


def get_last_error(scraper_id: str) -> str:
    """Get stderr_tail from the most recent failed run.

    Also writes it to /fleet-data/{scraper_id}/last_error.txt so the
    dev-agent can read it without env-var escaping issues.
    """
    error_text = ""
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """SELECT stderr_tail FROM scraper_runs
               WHERE scraper_id = %s AND exit_code != 0
               ORDER BY started_at DESC LIMIT 1""",
            (scraper_id,),
        )
        row = cur.fetchone()
        conn.close()
        error_text = row[0] if row else ""
    except Exception as e:
        log.warning("Failed to query last error for %s: %s", scraper_id, e)

    error_file = FLEET_DATA / scraper_id / "last_error.txt"
    try:
        error_file.write_text(error_text)
    except OSError as e:
        log.warning("Failed to write last_error.txt for %s: %s", scraper_id, e)

    return error_text
