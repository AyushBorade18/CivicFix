#!/usr/bin/env bash
# The whole local stack in one command: database, dev sign-in keys, API
# (auto-reloads on code changes) and both frontends. Anything already running
# is left alone. Ctrl-C stops what this script started.
#
#   scripts/dev.sh
#
# Override PG_CTL / PG_DATA / PG_PORT if your Postgres lives elsewhere.
set -euo pipefail
cd "$(dirname "$0")/.."

PG_CTL=${PG_CTL:-/opt/homebrew/opt/postgresql@17/bin/pg_ctl}
PG_DATA=${PG_DATA:-/opt/homebrew/var/postgresql@17-civicfix}
PG_PORT=${PG_PORT:-5433}

listening() { lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1; }

trap 'kill 0' EXIT  # stop every child of this script on exit

if ! pg_isready -h localhost -p "$PG_PORT" -q; then
  echo "Starting Postgres on :$PG_PORT"
  "$PG_CTL" -D "$PG_DATA" -o "-p $PG_PORT" -l "$PG_DATA/server.log" start
fi

source .venv/bin/activate

if [ -d .dev_auth/public ] && ! listening 8765; then
  echo "Serving dev sign-in keys on :8765"
  python -m http.server 8765 --bind 127.0.0.1 --directory .dev_auth/public >/dev/null 2>&1 &
fi

if listening 8000; then
  echo "API already running on :8000 (left alone)"
else
  uvicorn app.api.main:app --reload --port 8000 &
fi

if listening 5173 || listening 5174; then
  echo "Frontend dev servers already running on :5173/:5174 (left alone)"
else
  (cd web && npm run dev) &
fi

echo "Citizen site: http://localhost:5173   Staff Command Center: http://localhost:5174"
wait
