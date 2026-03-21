#!/bin/sh

# Ensure files created in shared volumes are world-readable/writable
umask 000

# Start crond in the background
cron

# Start the FastAPI server in the foreground
exec python -m uvicorn server:app --host 0.0.0.0 --port 8000
