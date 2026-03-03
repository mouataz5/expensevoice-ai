#!/usr/bin/env bash
# Production deploy script — pull latest code, build, and restart containers.
# Run from repository root: ./scripts/deploy-prod.sh

set -e

cd "$(dirname "$0")/.."

echo "==> Pulling latest code..."
git pull origin main

echo "==> Building and starting containers..."
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

echo "==> Done. Check app: https://app.abesagrotech.tn (or http if no SSL yet)"
