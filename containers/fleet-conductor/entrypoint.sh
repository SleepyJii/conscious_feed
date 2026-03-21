#!/bin/sh

# Start crond in the background
cron

# Start the FastAPI server in the foreground
exec python -m uvicorn api:app --host 0.0.0.0 --port 8000
