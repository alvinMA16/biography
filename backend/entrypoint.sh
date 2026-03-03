#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
for i in $(seq 1 60); do
    if python -c "import os, psycopg2; psycopg2.connect(os.environ['DATABASE_URL'])" 2>/dev/null; then
        echo "PostgreSQL is ready!"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: PostgreSQL not ready after 60 seconds"
        exit 1
    fi
    sleep 1
done

echo "Checking for pending Alembic migrations..."
PENDING=$(alembic check 2>&1 || true)
if echo "$PENDING" | grep -q "New upgrade"; then
    echo "检测到待执行迁移，先备份数据库..."
    BACKUP_FILE="/backups/pre_migration_$(date +%Y%m%d_%H%M%S).sql.gz"
    mkdir -p /backups
    pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"
    echo "备份完成: $BACKUP_FILE"
fi

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
