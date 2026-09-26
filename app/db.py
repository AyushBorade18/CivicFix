import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def get_db():
    """FastAPI dependency: one connection per request, always closed."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
