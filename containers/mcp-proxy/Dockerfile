FROM python:3.11-slim

RUN pip install --no-cache-dir "mcp[cli]" httpx

WORKDIR /app
COPY mcp_proxy.py .

EXPOSE 8080

ENTRYPOINT ["python3", "mcp_proxy.py"]
