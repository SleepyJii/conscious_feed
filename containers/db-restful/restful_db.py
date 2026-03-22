import json
import yaml
from xml.etree.ElementTree import Element, SubElement, tostring

import psycopg2
import psycopg2.extras
from flask import Flask, request, make_response, jsonify

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def open_db_conn():
    try:
        conn = psycopg2.connect(
            host="db",
            database="scrape_db",
            user="conscious_feed",
            password="conscious_feed",
            port=5432,
        )
        return conn
    except Exception as e:
        print(f"error: {e}")
        return None


# ---------------------------------------------------------------------------
# Generic SQL (legacy)
# ---------------------------------------------------------------------------

@app.route("/db_execute", methods=["POST"])
def db_execute():
    conn = open_db_conn()
    if conn is None:
        return make_response("Database connection failed", 500)

    cursor = conn.cursor()
    command = request.form.get("command")
    if not command:
        cursor.close()
        conn.close()
        return make_response("Missing parameter: command", 400)

    cursor.execute(command)
    if cursor.description is None:
        conn.commit()
        cursor.close()
        conn.close()
        return make_response("Command executed successfully", 200)

    ret = cursor.fetchall()
    cursor.close()
    conn.close()
    return make_response(jsonify(ret), 200)


# ---------------------------------------------------------------------------
# RSS content (scrape_results)
# ---------------------------------------------------------------------------

@app.route("/rss_content", methods=["GET"])
def rss_content():
    """Return scraped content, optionally filtered by scraper_id.

    Query params:
        scraper_id  — filter to a single scraper
        limit       — max rows (default 100)
        offset      — pagination offset (default 0)
    """
    conn = open_db_conn()
    if conn is None:
        return make_response("Database connection failed", 500)

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    scraper_id = request.args.get("scraper_id")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    if scraper_id:
        cursor.execute(
            """SELECT id, scraper_id, scraper_name, category, target_url, page_url,
                      title, content, published_at, scraped_at
               FROM scrape_results
               WHERE scraper_id = %s
               ORDER BY COALESCE(published_at, scraped_at) DESC
               LIMIT %s OFFSET %s""",
            (scraper_id, limit, offset),
        )
    else:
        cursor.execute(
            """SELECT id, scraper_id, scraper_name, category, target_url, page_url,
                      title, content, published_at, scraped_at
               FROM scrape_results
               ORDER BY COALESCE(published_at, scraped_at) DESC
               LIMIT %s OFFSET %s""",
            (limit, offset),
        )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# RSS feed (XML)
# ---------------------------------------------------------------------------

def _rfc822(dt) -> str:
    """Format a datetime as RFC 822 for RSS pubDate."""
    if dt is None:
        return ""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _feed_query():
    """Shared query logic for /rss and /json endpoints.

    Reads source, category, search, limit from request.args.
    Returns (rows, source, category) or raises 500.
    """
    conn = open_db_conn()
    if conn is None:
        return None, None, None

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = []
    params = []

    source = request.args.get("source")
    if source:
        conditions.append("scraper_id = %s")
        params.append(source)

    category = request.args.get("category")
    if category:
        conditions.append("category = %s")
        params.append(category)

    search = request.args.get("search")
    if search:
        conditions.append("(title ILIKE %s OR content ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    limit = request.args.get("limit", 50, type=int)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    cursor.execute(
        f"""SELECT scraper_id, scraper_name, category, target_url, page_url,
                   title, content, published_at, scraped_at
            FROM scrape_results
            {where}
            ORDER BY COALESCE(published_at, scraped_at) DESC
            LIMIT %s""",
        (*params, limit),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows, source, category


@app.route("/yaml", methods=["GET"])
def yaml_feed():
    """Return scraped content as YAML.

    Query params: same as /rss — source, category, search, limit.
    """
    rows, source, category = _feed_query()
    if rows is None:
        return make_response("Database connection failed", 500)
    resp = make_response(yaml.dump([dict(r) for r in rows], default_flow_style=False, allow_unicode=True))
    resp.headers["Content-Type"] = "text/yaml; charset=utf-8"
    return resp


@app.route("/json", methods=["GET"])
def json_feed():
    """Return scraped content as a JSON feed.

    Query params: same as /rss — source, category, search, limit.
    """
    rows, source, category = _feed_query()
    if rows is None:
        return make_response("Database connection failed", 500)
    return jsonify([dict(r) for r in rows])


@app.route("/rss", methods=["GET"])
def rss_feed():
    """Return scraped content as an RSS 2.0 XML feed.

    Query params: source, category, search, limit (default 50).
    """
    rows, source, category = _feed_query()
    if rows is None:
        return make_response("Database connection failed", 500)

    # Build RSS 2.0 XML
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    # Build a readable title describing the query
    search = request.args.get("search")
    filters = []
    if rows and source:
        filters.append(rows[0].get("scraper_name") or source)
    elif source:
        filters.append(source)
    if category:
        filters.append(f"#{category}")
    if search:
        filters.append(f'"{search}"')

    if filters:
        title = f"Conscious Feed — {', '.join(filters)}"
    else:
        title = "Conscious Feed — All Items"
    SubElement(channel, "title").text = title
    SubElement(channel, "description").text = "AI-hybridized RSS bridge"
    SubElement(channel, "link").text = f"/rss{('?' + request.query_string.decode()) if request.query_string else ''}"

    for row in rows:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = row["title"] or "Untitled"
        SubElement(item, "link").text = row["page_url"] or row["target_url"] or ""
        SubElement(item, "description").text = row["content"] or ""
        SubElement(item, "source").text = row["scraper_name"] or row["scraper_id"]
        if row.get("category"):
            SubElement(item, "category").text = row["category"]
        pub_date = row.get("published_at") or row.get("scraped_at")
        if pub_date:
            SubElement(item, "pubDate").text = _rfc822(pub_date)
        SubElement(item, "guid", isPermaLink="false").text = (
            f"{row['scraper_id']}:{row['page_url'] or ''}:{row['title'] or ''}"
        )

    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode").encode("utf-8")
    resp = make_response(xml_bytes)
    resp.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
    return resp


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.route("/register_event", methods=["POST"])
def register_event():
    """Insert a new event.

    JSON body:
        source        — (required) container/service that produced the event
        event_type    — (required) event category
        container_id  — (optional) scraper job reference
        event_payload — (optional) arbitrary JSON data, defaults to {}
    """
    conn = open_db_conn()
    if conn is None:
        return make_response("Database connection failed", 500)

    data = request.get_json(silent=True)
    if not data:
        return make_response("Missing JSON body", 400)

    source = data.get("source")
    event_type = data.get("event_type")
    if not source or not event_type:
        return make_response("Missing required fields: source, event_type", 400)

    container_id = data.get("container_id")
    event_payload = data.get("event_payload", {})

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """INSERT INTO events (source, container_id, event_type, event_payload)
           VALUES (%s, %s, %s, %s::jsonb)
           RETURNING event_id, created_at, source, container_id, event_type, event_payload""",
        (source, container_id, event_type, json.dumps(event_payload)),
    )
    row = dict(cursor.fetchone())
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(row), 201


@app.route("/find_events", methods=["GET"])
def find_events():
    """Query events with optional filters.

    Query params:
        source        — filter by source
        event_type    — filter by event type
        container_id  — filter by container/scraper id
        limit         — max rows (default 100)
        offset        — pagination offset (default 0)
    """
    conn = open_db_conn()
    if conn is None:
        return make_response("Database connection failed", 500)

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = []
    params = []

    source = request.args.get("source")
    if source:
        conditions.append("source = %s")
        params.append(source)

    event_type = request.args.get("event_type")
    if event_type:
        conditions.append("event_type = %s")
        params.append(event_type)

    container_id = request.args.get("container_id")
    if container_id:
        conditions.append("container_id = %s")
        params.append(container_id)

    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    cursor.execute(
        f"""SELECT event_id, created_at, source, container_id, event_type, event_payload
            FROM events
            {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s""",
        (*params, limit, offset),
    )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
