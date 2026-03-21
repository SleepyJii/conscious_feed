# Use an official lightweight Python image
FROM python:3.11-slim

# Install Node.js and dependencies for Playwright browsers
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    fonts-liberation \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    nodejs \
    npm \
    jq \
    postgresql-client \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir playwright

# Copy playwright-server and install Node.js dependencies
COPY playwright-server/ ./playwright-server/
RUN cd playwright-server && npm install

# Install Playwright browsers (shared by both Node.js and Python)
RUN npx playwright install --with-deps

# Copy application code
COPY scrape.py ./

# Copy startup and ingestion scripts
COPY entrypoint.sh ingest.sh ./
RUN chmod +x entrypoint.sh ingest.sh

ENTRYPOINT ["./entrypoint.sh"]
