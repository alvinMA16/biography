#!/bin/bash
set -e

echo "Starting Doubao Realtime Service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 9000
