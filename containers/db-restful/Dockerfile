FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask psycopg2-binary

COPY . .

EXPOSE 5000

ENTRYPOINT ["python", "restful_db.py"]
