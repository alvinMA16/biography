#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
for i in $(seq 1 60); do
    if python -c "
import psycopg2
try:
    psycopg2.connect('$DATABASE_URL')
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        echo "PostgreSQL is ready!"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: PostgreSQL not ready after 60 seconds"
        exit 1
    fi
    sleep 1
done

echo "Running Alembic migrations..."
alembic upgrade head

WORKERS=${WORKERS:-2}
echo "Starting application with $WORKERS workers..."
exec gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "$WORKERS" \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
