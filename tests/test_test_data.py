"""Generated test complaints (reports.is_synthetic) must never reach the live
site. With SHOW_TEST_DATA off - the default for any deployment - every read
path behaves as if an issue made only of test reports does not exist.
Verified against SQL ground truth on the real database.
"""
import pytest

from tests.test_api import real_admin, real_client, real_conn  # noqa: F401

REAL_ISSUE_IDS_SQL = (
    "SELECT i.id FROM issues i WHERE EXISTS "
    "(SELECT 1 FROM reports r WHERE r.issue_id = i.id AND NOT r.is_synthetic)"
)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("SHOW_TEST_DATA", "0")


def _ids(real_conn, sql):
    with real_conn.cursor() as cur:
        cur.execute(sql)
        return {r[0] for r in cur.fetchall()}


def test_live_site_hides_test_issues_everywhere(live, real_client, real_conn):
    real_ids = _ids(real_conn, REAL_ISSUE_IDS_SQL)
    test_ids = _ids(real_conn, "SELECT id FROM issues") - real_ids
    assert test_ids, "precondition: the dev database holds generated test issues"
    test_id = min(test_ids)

    staff = real_client.get("/api/issues", params={"limit": 200}).json()
    assert staff["total"] == len(real_ids)
    assert {i["issue_id"] for i in staff["items"]} <= real_ids

    assert {i["issue_id"] for i in real_client.get("/api/map").json()["issues"]} <= real_ids
    assert real_client.get(f"/api/issues/{test_id}").status_code == 404

    public = real_client.get("/api/public/issues", params={"limit": 200}).json()
    assert public["total"] == len(real_ids)
    assert {i["issue_id"] for i in real_client.get("/api/public/map").json()["issues"]} <= real_ids
    assert real_client.get(f"/api/public/issues/{test_id}").status_code == 404

    stats = real_client.get("/api/stats").json()
    assert stats["issues"] == len(real_ids)
    assert stats["reports"] == len(_ids(real_conn, "SELECT id FROM reports WHERE NOT is_synthetic"))

    matches = real_client.get("/api/matches", params={"limit": 500}).json()
    assert {m["issue_id"] for m in matches} <= real_ids


def test_dev_flag_shows_test_issues(monkeypatch, real_client, real_conn):
    monkeypatch.setenv("SHOW_TEST_DATA", "1")
    total = len(_ids(real_conn, "SELECT id FROM issues"))
    assert real_client.get("/api/issues", params={"limit": 1}).json()["total"] == total
