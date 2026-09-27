import os

from dotenv import load_dotenv

# Tests must never touch the real `civicfix` database - point every app.db
# connection at the isolated `civicfix_test` database instead, before
# app.db (or anything importing it) gets imported below. See git history:
# an earlier test run's TRUNCATE wiped a real, expensively-geocoded
# ingestion because tests and dev data shared one database.
load_dotenv()
# Saved before the override below, so tests that must deliberately verify
# against the real seeded dataset (e.g. the API tests) can restore it via
# monkeypatch.setattr("app.db.DATABASE_URL", REAL_DATABASE_URL) for the
# duration of just those tests.
REAL_DATABASE_URL = os.environ["DATABASE_URL"]
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
# Fixtures are generated test data; tests/test_test_data.py switches this off
# to check the live-site behaviour.
os.environ.setdefault("SHOW_TEST_DATA", "1")
# LLM triage (app/nlp/triage.py) is off without a key, so no test ever calls
# the paid API; tests/test_triage.py sets a fake key around a fake client.
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.ingest.wards import load_wards  # noqa: E402
from app.migrate import migrate  # noqa: E402

WARDS_GEOJSON = "data/wards/pune-2022-wards.geojson"


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_wards():
    load_wards(WARDS_GEOJSON)
    # Bring the test database's schema up to date (users, report ownership...).
    migrate()


@pytest.fixture(scope="session")
def real_database_url() -> str:
    """The real civicfix DATABASE_URL, for tests that must deliberately
    verify against the real seeded dataset. Exposed as a fixture rather
    than a plain module constant: `from tests.conftest import X` can make
    pytest import this module a second time under a different module
    identity, re-running the override above and clobbering a plain
    constant's captured value. A fixture is always resolved through
    pytest's own already-loaded conftest instance, so it can't do that.
    """
    return REAL_DATABASE_URL


@pytest.fixture
def db_conn():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def clean_wards(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE wards CASCADE")
    db_conn.commit()
    yield db_conn
    load_wards(WARDS_GEOJSON)


@pytest.fixture
def clean_works(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE works CASCADE")
    db_conn.commit()
    yield db_conn


@pytest.fixture
def clean_reports(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE reports CASCADE")
    db_conn.commit()
    yield db_conn
