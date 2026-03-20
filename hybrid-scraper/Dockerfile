# Use an official lightweight Python image
FROM python:3.11-slim

# Install necessary dependencies for Playwright browsers
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
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt if you have one (optional)
# COPY requirements.txt .

# Install Python dependencies including Playwright
# If you have a requirements.txt, use:
# RUN pip install --no-cache-dir -r requirements.txt

# Otherwise, install playwright directly:
RUN pip install --no-cache-dir playwright

# Install Playwright browsers
RUN playwright install --with-deps

# Copy your application code (optional)
# COPY . .

# Default command (optional)
ENTRYPOINT ["sh"]

