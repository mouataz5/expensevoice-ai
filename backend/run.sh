#!/usr/bin/env bash
# Run from backend/ or project root. Starts the FastAPI server.

set -e
cd "$(dirname "$0")"

if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "Installing dependencies..."
  pip3 install -r requirements.txt
fi

echo "Starting backend on http://localhost:8000"
exec python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
