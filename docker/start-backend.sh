#!/bin/sh
set -e

cd /app
uv run --directory backend alembic upgrade head
exec uv run --directory backend gunicorn \
    --bind 0.0.0.0:5000 \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads "${WEB_THREADS:-8}" \
    --timeout "${WEB_TIMEOUT:-300}" \
    --access-logfile - \
    --error-logfile - \
    app:app
