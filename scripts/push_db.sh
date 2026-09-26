#!/usr/bin/env bash
# Copy the local civicfix database (schema + data + applied migrations) into a
# hosted Postgres such as Supabase.
#
#   TARGET_DATABASE_URL='postgresql://...' scripts/push_db.sh
#
# The target must be EMPTY. Extensions are created up front in `public` and left
# out of the restore itself: hosted Postgres doesn't let a restore own them, and
# the dump refers to public.geometry / public.vector.
set -euo pipefail

PG=/opt/homebrew/opt/postgresql@17/bin   # v17 client, matches the local server
SOURCE_URL=${SOURCE_DATABASE_URL:-postgresql://localhost:5433/civicfix}
# Defaults to DEPLOY_DATABASE_URL from .env (the Supabase session pooler URI).
if [ -z "${TARGET_DATABASE_URL:-}" ] && [ -f .env ]; then
  TARGET_DATABASE_URL=$(grep -E '^DEPLOY_DATABASE_URL=' .env | cut -d= -f2-)
fi
: "${TARGET_DATABASE_URL:?fill DEPLOY_DATABASE_URL in .env (or set TARGET_DATABASE_URL)}"

DUMP=$(mktemp -t civicfix-push).dump
LIST=$(mktemp -t civicfix-push).list
trap 'rm -f "$DUMP" "$LIST"' EXIT

echo "dumping $SOURCE_URL"
"$PG/pg_dump" -Fc --no-owner --no-privileges -d "$SOURCE_URL" -f "$DUMP"
"$PG/pg_restore" -l "$DUMP" | grep -v -E ' EXTENSION | COMMENT - EXTENSION ' > "$LIST"

echo "preparing extensions on target"
"$PG/psql" -v ON_ERROR_STOP=1 -q -d "$TARGET_DATABASE_URL" \
  -c "CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public" \
  -c "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"

echo "restoring"
"$PG/pg_restore" --no-owner --no-privileges --exit-on-error -L "$LIST" -d "$TARGET_DATABASE_URL" "$DUMP"

echo "row counts (source -> target)"
for t in wards works issues reports matches signals feedback users evidence schema_migrations; do
  s=$("$PG/psql" -Atq -d "$SOURCE_URL" -c "SELECT count(*) FROM $t")
  d=$("$PG/psql" -Atq -d "$TARGET_DATABASE_URL" -c "SELECT count(*) FROM $t")
  printf '%-18s %6s -> %6s %s\n' "$t" "$s" "$d" "$([ "$s" = "$d" ] && echo ok || echo MISMATCH)"
done
