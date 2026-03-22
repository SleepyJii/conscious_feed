FROM postgres:16
RUN apt-get update && apt-get install -y postgresql-16-cron && rm -rf /var/lib/apt/lists/*
COPY entrypoint.sh /usr/local/bin/custom-entrypoint.sh

ENTRYPOINT ["custom-entrypoint.sh"]
