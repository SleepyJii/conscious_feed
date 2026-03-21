FROM python:3.11-slim

# System tools for debugging and socket bridging
RUN apt-get update && apt-get install -y --no-install-recommends \
    socat curl jq \
    && rm -rf /var/lib/apt/lists/*

# Playwright + browser
RUN pip install --no-cache-dir playwright psycopg2-binary requests "mcp[cli]"
RUN playwright install --with-deps chromium

WORKDIR /app

COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
