#!/usr/bin/env bash
# reset-dev.sh — wipe the dev database and restart the app
#
# Supports both setups:
#   - Docker Compose (Postgres): stops stack, removes volume, restarts
#   - Local SQLite: deletes .db file, reruns migrations
#
# Usage: ./scripts/reset-dev.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ---------------------------------------------------------------------------
# Detect database backend from .env (falls back to .env.example default)
# ---------------------------------------------------------------------------
DATABASE_URL=""
if [ -f .env ]; then
  DATABASE_URL=$(grep -E "^DATABASE_URL=" .env | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
fi

if [ -z "$DATABASE_URL" ]; then
  echo "No .env found — defaulting to SQLite (bilancio.db)."
  DATABASE_URL="sqlite+aiosqlite:///./bilancio.db"
fi

# ---------------------------------------------------------------------------
# SQLite path
# ---------------------------------------------------------------------------
if [[ "$DATABASE_URL" == sqlite* ]]; then
  # Extract file path: strip driver prefix and leading ./
  DB_FILE="${DATABASE_URL#sqlite+aiosqlite:///}"
  DB_FILE="${DB_FILE#./}"

  echo "==> Killing any process on port 8000 ..."
  lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "    Killed." || echo "    Nothing running on 8000."

  echo "==> SQLite mode: removing $DB_FILE ..."
  rm -f "$DB_FILE"

  echo "==> Running migrations ..."
  uv run alembic upgrade head

  echo "==> Starting uvicorn ..."
  uv run uvicorn bilancio.main:app --reload
fi

# ---------------------------------------------------------------------------
# Docker / Postgres path
# ---------------------------------------------------------------------------
echo "==> Stopping Docker stack ..."
docker compose down

echo "==> Wiping Postgres data volume ..."
docker volume rm bilancio_postgres_data 2>/dev/null \
  && echo "    Volume removed." \
  || echo "    Volume not found — already clean."

echo "==> Restarting stack (migrations run automatically on startup) ..."
docker compose up
