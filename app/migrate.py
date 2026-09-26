"""Apply migrations/*.sql in filename order, each exactly once.

schema.sql creates a fresh database; migrations change an existing one
without recreating it. Applied names are recorded in schema_migrations,
and each file runs inside the same transaction as its record, so a failed
migration leaves nothing half-applied.

Run: python -m app.migrate
"""
from pathlib import Path

from app.db import get_connection

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def migrate(conn=None) -> list[str]:
    own_conn = conn is None
    conn = conn or get_connection()
    applied = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT name FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in done:
                    continue
                cur.execute(path.read_text())
                cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied.append(path.name)
        conn.commit()
    finally:
        if own_conn:
            conn.close()
    return applied


if __name__ == "__main__":
    names = migrate()
    print(f"applied: {', '.join(names)}" if names else "already up to date")
