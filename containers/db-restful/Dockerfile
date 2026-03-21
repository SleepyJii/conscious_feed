FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir flask psycopg2-binary

COPY . .

EXPOSE 5000

ENTRYPOINT ["python", "restful_db.py"]
