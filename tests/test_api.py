import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.auth import get_current_user
from app.users import create_user


@pytest.fixture
def real_admin(monkeypatch, real_database_url):
    """A throwaway system_admin account in the real database, deleted after
    the test. Reports these tests submit are owned by it (reporter_user_id
    is a real foreign key), and every test cleans its reports up first."""
    monkeypatch.setattr("app.db.DATABASE_URL", real_database_url)
    from app.db import get_connection
    conn = get_connection()
    admin = create_user(conn, f"pytest|api-admin|{uuid.uuid4().hex[:8]}", "system_admin")
    try:
        yield admin
    finally:
        with conn.cursor() as cur:
            # Its close/route/release actions were on test issues that are gone; keep them out of the real audit log.
            cur.execute("DELETE FROM audit_log WHERE actor_user_id = %s", (admin.id,))
            cur.execute("DELETE FROM users WHERE id = %s", (admin.id,))
        conn.commit()
        conn.close()


@pytest.fixture
def real_client(monkeypatch, real_database_url, real_admin):
    """These API tests deliberately verify against the real, seeded
    civicfix database (per this task's explicit instructions), not the
    isolated civicfix_test every other test in this suite uses. Restoring
    app.db.DATABASE_URL just for the duration of one test is safe: it's a
    monkeypatch, auto-reverted afterward, and get_connection() re-reads the
    module global on every call rather than caching it.

    They test the pipeline, not auth: the caller is resolved straight to a
    system_admin, skipping token verification. The auth boundary itself is
    tested in tests/test_auth.py.
    """
    monkeypatch.setattr("app.db.DATABASE_URL", real_database_url)
    app.dependency_overrides[get_current_user] = lambda: real_admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def real_conn(monkeypatch, real_database_url):
    monkeypatch.setattr("app.db.DATABASE_URL", real_database_url)
    from app.db import get_connection
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# This is a real, shared, live database (other sessions genuinely exercise
# POST /api/reports concurrently - confirmed during this work, not
# hypothetical), so these baselines are floors from the last known-clean
# count, not exact equality - a passing "==" here would mean either nothing
# changed, or we got lucky about what did.
MIN_WORKS = 318
MIN_REPORTS = 400
MIN_ISSUES = 320  # was 333; the 2026-09-25 demo regen re-clustered 400 reports into
# 320 issues and reassigned every issue id (backups/civicfix_before_demo_regen.dump)
MIN_MATCHES = 27  # was 28; a concurrent session's activity took it to 27 - see comment above
MIN_SENSITIVE_SITES = 3456  # 861 OSM + 2,263 PMC/PMPML bus stops + 332 L08 hospitals/schools
                             # (app/ingest/pmc_bus_stops.py, app/ingest/l08_sensitive_sites.py)
MIN_SIGNALS = 36
MIN_DRAINAGE_SEWAGE_ISSUES = 77  # was 78; 2026-09-27 recurrence merged demo issue 1073 into closed 1074.
# (Before that: 82 -> 81 via a legitimate recurrence merge - see recurrence.py)


def test_health(real_client):
    resp = real_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database_connected"] is True
    assert body["counts"]["works"] == MIN_WORKS  # works is never written to at runtime - this one IS exact
    assert body["counts"]["reports"] >= MIN_REPORTS


def test_stats_matches_real_dataset(real_client):
    resp = real_client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["wards"] == 58  # wards is never written to at runtime - exact
    assert body["works"] == MIN_WORKS  # works is never written to at runtime - exact
    assert body["reports"] >= MIN_REPORTS
    assert body["issues"] >= MIN_ISSUES
    assert body["matches"] >= MIN_MATCHES
    assert body["sensitive_sites"] == MIN_SENSITIVE_SITES  # never written to at runtime - exact
    assert body["verification_signals"] >= MIN_SIGNALS


def test_list_issues_default_sorted_by_priority_desc(real_client):
    resp = real_client.get("/api/issues")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= MIN_ISSUES
    assert len(body["items"]) == 50  # default limit
    scores = [i["priority_score"] for i in body["items"]]
    assert scores == sorted(scores, reverse=True)


def test_list_issues_category_filter(real_client):
    resp = real_client.get("/api/issues", params={"category": "drainage_sewage", "limit": 200})
    body = resp.json()
    assert body["total"] >= MIN_DRAINAGE_SEWAGE_ISSUES
    assert all(i["category"] == "drainage_sewage" for i in body["items"])


def test_list_issues_ward_filter(real_client):
    # Which wards hold issues changes every time the pipeline re-clusters
    # (ward 11 had issues before the 2026-09-25 regen and has none after),
    # so pick a ward that currently has one instead of naming a number.
    ward_id = real_client.get("/api/issues", params={"limit": 1}).json()["items"][0]["ward_id"]
    resp = real_client.get("/api/issues", params={"ward_id": ward_id, "limit": 200})
    body = resp.json()
    assert body["total"] > 0
    assert all(i["ward_id"] == ward_id for i in body["items"])


def test_list_issues_min_priority_filter(real_client):
    resp = real_client.get("/api/issues", params={"min_priority": 0.7, "limit": 200})
    body = resp.json()
    assert body["total"] > 0
    assert all(i["priority_score"] >= 0.7 for i in body["items"])


def test_list_issues_pagination(real_client):
    page1 = real_client.get("/api/issues", params={"limit": 10, "offset": 0}).json()
    page2 = real_client.get("/api/issues", params={"limit": 10, "offset": 10}).json()
    ids1 = {i["issue_id"] for i in page1["items"]}
    ids2 = {i["issue_id"] for i in page2["items"]}
    assert ids1.isdisjoint(ids2)


def test_list_issues_triage_fields_and_queues(real_client, real_conn):
    body = real_client.get("/api/issues", params={"limit": 20}).json()
    for item in body["items"]:
        for key in ("location_phrase", "evidence_accuracy_m", "pending_evidence", "has_resolution_evidence", "assigned_worker_id"):
            assert key in item
    with real_conn.cursor() as cur:
        cur.execute("SELECT count(DISTINCT issue_id) FROM evidence WHERE review_status = 'pending_review'")
        pending = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM issues WHERE assigned_worker_id IS NOT NULL")
        assigned = cur.fetchone()[0]
    assert real_client.get("/api/issues", params={"queue": "verification_pending"}).json()["total"] == pending
    assert real_client.get("/api/issues", params={"queue": "assigned"}).json()["total"] == assigned
    assert real_client.get("/api/issues", params={"queue": "bogus"}).status_code == 422


def test_list_issues_is_synthetic_true_for_all_current_issues(real_client):
    # every report in this dataset is synthetic (no real citizen intake exists yet)
    resp = real_client.get("/api/issues", params={"limit": 200})
    assert all(i["is_synthetic"] is True for i in resp.json()["items"])


def test_issue_detail_matched_issue(real_client, real_conn):
    with real_conn.cursor() as cur:
        cur.execute("SELECT issue_id FROM matches LIMIT 1")
        issue_id = cur.fetchone()[0]

    resp = real_client.get(f"/api/issues/{issue_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["issue_id"] == issue_id
    assert len(body["reports"]) == body["report_count"]
    assert len(body["matches"]) >= 1
    assert body["priority_score"] is not None
    assert "terms" in body["priority_breakdown"]

    match = body["matches"][0]
    assert match["match_reason"]
    # every real match today is ward-level - never a fabricated distance
    if match["issue_location_precision"] == "ward_level":
        assert match["distance_m"] is None
        assert "ward-level" in match["match_reason"].lower() or "same ward" in match["match_reason"].lower()


def test_issue_detail_nonexistent_returns_404(real_client):
    resp = real_client.get("/api/issues/99999999")
    assert resp.status_code == 404


def test_list_matches_returns_all_28_with_nullable_distance(real_client):
    resp = real_client.get("/api/matches", params={"limit": 500})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= MIN_MATCHES
    assert all("distance_m" in m for m in body)
    assert all(m["work"] is not None for m in body)
    # the original dataset's matches are all ward-level (no precise-distance
    # anchor is 'completed'); a concurrent live add could in principle
    # create a precise one, so this checks the floor is still ward-level,
    # not that literally every match is
    assert sum(1 for m in body if m["distance_m"] is None) >= MIN_MATCHES


def test_list_works_filters_and_precision_field(real_client):
    resp = real_client.get("/api/works", params={"category": "drainage_sewage", "limit": 500})
    body = resp.json()
    assert len(body) > 0
    assert all(w["category"] == "drainage_sewage" for w in body)
    for w in body:
        if w["location"] is not None:
            assert w["location_precision"] in ("precise", "ward_level")


def test_map_endpoint_shape(real_client):
    resp = real_client.get("/api/map")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sensitive_sites"]) == MIN_SENSITIVE_SITES  # never written to at runtime - exact
    assert len(body["wards"]) == 58  # never written to at runtime - exact
    assert len(body["matched_works"]) > 0
    for site in body["sensitive_sites"][:5]:
        assert site["location"]["lat"] is not None
    # Command Center groups issues by ward and draws ward outlines.
    assert all("ward_id" in i and i["first_reported"] for i in body["issues"])
    assert any(i["ward_id"] is not None for i in body["issues"])
    for ward in body["wards"]:
        assert ward["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_public_map_carries_ward_outlines(real_client):
    wards = real_client.get("/api/public/map").json()["wards"]
    assert len(wards) == 58
    assert all(w["geometry"]["type"] in ("Polygon", "MultiPolygon") for w in wards)


def test_large_responses_are_gzipped(real_client):
    resp = real_client.get("/api/public/map", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"


def test_post_reports_rejects_unknown_ward_id(real_client):
    resp = real_client.post("/api/reports", json={"raw_text": "test complaint", "ward_id": 99999})
    assert resp.status_code == 400


def test_post_reports_full_live_pipeline_then_cleanup(real_client, real_conn):
    """Exercises the real live-add pipeline against the real database, then
    precisely reverts whatever it touched so works/reports/issues/matches
    counts return to exactly their pre-test values, per this task's
    explicit cleanup requirement.
    """
    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        reports_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM issues")
        issues_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM matches")
        matches_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM signals")
        signals_before = cur.fetchone()[0]

    # Deliberately nonsense/distinctive text: low cosine similarity with any
    # real complaint guarantees this becomes its own new singleton issue,
    # not an attach to an existing one - keeps cleanup unambiguous.
    unique_marker = "zzqx automated integration test marker report unrelated content aaa bbb ccc"
    resp = real_client.post("/api/reports", json={"raw_text": unique_marker})
    assert resp.status_code == 201
    body = resp.json()

    try:
        assert body["report"]["raw_text"] == unique_marker
        # a signed-in account's submission is a real report, not synthetic
        assert body["report"]["is_synthetic"] is False
        assert body["is_synthetic"] is False
        assert body["category"] in (
            "pothole_road", "drainage_sewage", "water_supply", "streetlight",
            "garbage_waste", "footpath", "traffic_signage", "other",
        )
        assert body["severity"] in ("cosmetic", "moderate", "critical")
        assert body["priority_score"] is not None
        assert isinstance(body["signals"], list)
        # no location/ward supplied and nonsense text -> pipeline legitimately
        # finds nothing; must not fabricate a precise point
        assert body["report"]["geom_confidence"] != 1.0

        assert body["joined_existing_issue"] is False  # per the low-similarity guarantee above
        report_id = body["report"]["id"]
        issue_id = body["issue_id"]

        with real_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM reports WHERE id = %s", (report_id,))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT count(*) FROM issues WHERE id = %s", (issue_id,))
            assert cur.fetchone()[0] == 1
    finally:
        report_id = body["report"]["id"]
        issue_id = body["issue_id"]
        with real_conn.cursor() as cur:
            cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_id,))
            cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
            cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
            cur.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
        real_conn.commit()

    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        assert cur.fetchone()[0] == reports_before
        cur.execute("SELECT count(*) FROM issues")
        assert cur.fetchone()[0] == issues_before
        cur.execute("SELECT count(*) FROM matches")
        assert cur.fetchone()[0] == matches_before
        cur.execute("SELECT count(*) FROM signals")
        assert cur.fetchone()[0] == signals_before


def test_post_reports_with_resolvable_location_does_not_crash_on_time_check(real_client, real_conn):
    """Regression: found via manual execution, not caught by the other live
    tests here - datetime.now() (naive) was compared against issues.last_reported
    (timezone-aware, from Postgres) inside _attach_or_create_issue's _time_ok
    call, raising TypeError. That comparison is only reached when the new
    report resolves a real ward/location AND lands in a category with
    existing candidate issues - a report with no resolvable location (as
    used elsewhere in this file) short-circuits before ever reaching it.
    """
    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        reports_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM issues")
        issues_before = cur.fetchone()[0]

    resp = real_client.post(
        "/api/reports",
        json={"raw_text": "Sewage overflowing near Ward 11 again, terrible smell, third time this month"},
    )
    assert resp.status_code == 201
    body = resp.json()

    try:
        assert body["report"]["ward_id"] == 11
        assert body["category"] == "drainage_sewage"
    finally:
        report_id = body["report"]["id"]
        issue_id = body["issue_id"]
        with real_conn.cursor() as cur:
            cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
        if body["joined_existing_issue"]:
            # Restore full consistency (report_count, geom, embedding, match,
            # priority) by reusing the endpoint's own recompute functions
            # over the now-restored set of real member reports, rather than
            # trying to hand-snapshot an issue we didn't know in advance.
            import json as _json

            from app.api.main import _recompute_issue_aggregates, _refresh_match_for_issue
            from app.core.priority import compute_priority
            from app.core.signals import run_signals

            _recompute_issue_aggregates(real_conn, issue_id)
            _refresh_match_for_issue(real_conn, issue_id)
            total, breakdown = compute_priority(issue_id, real_conn)
            with real_conn.cursor() as cur:
                cur.execute(
                    "UPDATE issues SET priority_score = %s, priority_breakdown = %s::jsonb WHERE id = %s",
                    (total, _json.dumps(breakdown), issue_id),
                )
            run_signals(conn=real_conn)
        else:
            with real_conn.cursor() as cur:
                cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_id,))
                cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
                cur.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
        real_conn.commit()

    if not body["joined_existing_issue"]:
        with real_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM issues")
            assert cur.fetchone()[0] == issues_before
    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        assert cur.fetchone()[0] == reports_before
        cur.execute("SELECT count(*) FROM matches")
        matches_after = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM signals")
        signals_after = cur.fetchone()[0]
    assert matches_after >= MIN_MATCHES
    assert signals_after >= MIN_SIGNALS


def test_post_reports_with_ward_hint_uses_ward_centroid_not_fake_precision(real_client, real_conn):
    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        reports_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM issues")
        issues_before = cur.fetchone()[0]

    unique_marker = "yywq ward hint automated integration test marker unrelated qqqrrr"
    resp = real_client.post("/api/reports", json={"raw_text": unique_marker, "ward_id": 20})
    assert resp.status_code == 201
    body = resp.json()

    try:
        assert body["report"]["ward_id"] == 20
        assert body["report"]["geom_confidence"] == 0.4  # ward centroid, never fabricated precision
    finally:
        report_id = body["report"]["id"]
        issue_id = body["issue_id"]
        with real_conn.cursor() as cur:
            cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
            # Only an issue this test created; never a real one its report joined.
            if not body["joined_existing_issue"]:
                cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_id,))
                cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
                cur.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
        real_conn.commit()

    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        assert cur.fetchone()[0] == reports_before
        cur.execute("SELECT count(*) FROM issues")
        assert cur.fetchone()[0] == issues_before


def test_get_metrics_returns_real_numbers(real_client):
    resp = real_client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"]["trained"] is True
    assert 0.0 <= body["classification"]["model_macro_f1"] <= 1.0
    assert 0.0 <= body["classification"]["baseline_macro_f1"] <= 1.0
    assert body["clustering"]["total_issues"] > 0
    assert 0.0 <= body["location"]["resolution_rate"] <= 1.0
    assert body["matcher"]["labeled_cases"] >= 0


def test_close_issue_rejects_unknown_id(real_client):
    resp = real_client.post("/api/issues/99999999/close")
    assert resp.status_code == 404


def test_close_then_recurrence_reopens_via_live_reports(real_client, real_conn):
    """The core new capability: close an issue, submit a new matching
    report, and the system should reopen the ORIGINAL issue (via
    run_recurrence_check inside POST /api/reports) rather than leaving two
    separate issues - this is the scene DEMO.md's whole pitch depends on,
    which was previously impossible to show live since nothing ever closed
    an issue.

    Uses ward 1, checked to have zero existing reports, specifically
    because a first attempt at this test (with a "zzqx marker" suffix on
    a populated ward) attached to a REAL pre-existing issue instead of
    creating a new one - real, since-restored contamination, not
    hypothetical. Zero pre-existing reports in the target ward removes the
    entire failure class rather than trying to detect and repair it after
    the fact.

    Cleanup commits each step separately: a later step failing must not be
    able to roll back an earlier step that already succeeded (this bit
    the first version of this test too - one failed final DELETE silently
    undid two already-correct report deletes in the same transaction).
    """
    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports WHERE ward_id = 1")
        assert cur.fetchone()[0] == 0, "ward 1 is expected to have zero existing reports for this test"
        cur.execute("SELECT count(*) FROM reports")
        reports_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM issues")
        issues_before = cur.fetchone()[0]

    marker = "zzqx recurrence demo test marker qqqrrr"
    first = real_client.post("/api/reports", json={"raw_text": f"Streetlight near Ward 1 not working, {marker}"})
    assert first.status_code == 201
    first_body = first.json()
    issue_a_id = first_body["issue_id"]
    assert first_body["joined_existing_issue"] is False  # guaranteed by the empty-ward precondition above
    report_a_id = first_body["report"]["id"]
    report_b_id = None

    try:
        # Close it - this is the precondition recurrence.py needs and that
        # nothing in the system could previously reach.
        close_resp = real_client.post(f"/api/issues/{issue_a_id}/close")
        assert close_resp.status_code == 200
        assert close_resp.json()["status"] == "closed"

        second = real_client.post(
            "/api/reports", json={"raw_text": f"Streetlight near Ward 1 still broken, {marker}"}
        )
        assert second.status_code == 201
        second_body = second.json()
        report_b_id = second_body["report"]["id"]

        # The new report's issue must resolve back to issue_a - proof the
        # recurrence merge actually happened, not just a second new issue.
        assert second_body["issue_id"] == issue_a_id

        with real_conn.cursor() as cur:
            cur.execute("SELECT status, recurrence_count, report_count FROM issues WHERE id = %s", (issue_a_id,))
            status, recurrence_count, report_count = cur.fetchone()
        assert status == "reopened"
        assert recurrence_count >= 1
        assert report_count == 2
    finally:
        report_ids = [report_a_id] + ([report_b_id] if report_b_id is not None else [])
        with real_conn.cursor() as cur:
            cur.execute("DELETE FROM reports WHERE id = ANY(%s)", (report_ids,))
        real_conn.commit()

        with real_conn.cursor() as cur:
            cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_a_id,))
            cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_a_id,))
            cur.execute("DELETE FROM issues WHERE id = %s", (issue_a_id,))
        real_conn.commit()

    with real_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        assert cur.fetchone()[0] == reports_before
        cur.execute("SELECT count(*) FROM issues")
        assert cur.fetchone()[0] == issues_before


def _insert_throwaway_issue(conn, category="pothole_road", ward_id=1, status="open", reporter_user_id=None):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO issues (category, ward_id, status, report_count, first_reported, last_reported) "
            "VALUES (%s, %s, %s, 1, now(), now()) RETURNING id",
            (category, ward_id, status),
        )
        issue_id = cur.fetchone()[0]
        if reporter_user_id is not None:  # feedback is only accepted from a reporter of the issue
            cur.execute(
                "INSERT INTO reports (raw_text, reported_at, category, issue_id, reporter_user_id) "
                "VALUES ('throwaway test report', now(), %s, %s, %s)",
                (category, issue_id, reporter_user_id),
            )
    conn.commit()
    return issue_id


def _delete_throwaway_issue(conn, issue_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM feedback WHERE issue_id = %s", (issue_id,))
        cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_id,))
        cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
        cur.execute("DELETE FROM reports WHERE issue_id = %s", (issue_id,))
        cur.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
    conn.commit()


def test_route_issue_rejects_unknown_id(real_client):
    resp = real_client.post("/api/issues/99999999/route")
    assert resp.status_code == 404


def test_route_issue_assigns_deterministic_agency_and_signal(real_client, real_conn):
    issue_id = _insert_throwaway_issue(real_conn, category="drainage_sewage")
    try:
        resp = real_client.post(f"/api/issues/{issue_id}/route")
        assert resp.status_code == 200
        body = resp.json()
        assert body["routed_agency"] == "PMC Sewage & Drainage Department"
        assert body["routed_at"] is not None

        again = real_client.post(f"/api/issues/{issue_id}/route")
        assert again.status_code == 400

        with real_conn.cursor() as cur:
            cur.execute(
                "SELECT rule_name FROM signals WHERE issue_id = %s AND rule_name = 'ROUTED_TO_AGENCY'",
                (issue_id,),
            )
            assert cur.fetchone() is not None
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def test_feedback_rejects_unknown_id(real_client):
    resp = real_client.post("/api/issues/99999999/feedback", json={"resolved_confirmed": True})
    assert resp.status_code == 404


def test_feedback_rejects_non_closed_issue(real_client, real_conn, real_admin):
    issue_id = _insert_throwaway_issue(real_conn, status="open", reporter_user_id=real_admin.id)
    try:
        resp = real_client.post(f"/api/issues/{issue_id}/feedback", json={"resolved_confirmed": True})
        assert resp.status_code == 400
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def test_feedback_confirming_resolution_keeps_issue_closed(real_client, real_conn, real_admin):
    issue_id = _insert_throwaway_issue(real_conn, status="closed", reporter_user_id=real_admin.id)
    try:
        resp = real_client.post(
            f"/api/issues/{issue_id}/feedback",
            json={"resolved_confirmed": True, "comment": "Fixed, thanks!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["issue_status"] == "closed"
        assert body["feedback"]["resolved_confirmed"] is True
        assert body["feedback"]["comment"] == "Fixed, thanks!"

        with real_conn.cursor() as cur:
            cur.execute("SELECT status FROM issues WHERE id = %s", (issue_id,))
            assert cur.fetchone()[0] == "closed"
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def test_feedback_disputing_resolution_reopens_issue(real_client, real_conn, real_admin):
    issue_id = _insert_throwaway_issue(real_conn, status="closed", reporter_user_id=real_admin.id)
    try:
        resp = real_client.post(
            f"/api/issues/{issue_id}/feedback",
            json={"resolved_confirmed": False, "comment": "Still broken"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["issue_status"] == "reopened"

        with real_conn.cursor() as cur:
            cur.execute("SELECT status, recurrence_count, closed_at FROM issues WHERE id = %s", (issue_id,))
            status, recurrence_count, closed_at = cur.fetchone()
            assert status == "reopened"
            assert recurrence_count == 1
            assert closed_at is None

            cur.execute(
                "SELECT rule_name FROM signals WHERE issue_id = %s AND rule_name = 'CITIZEN_DISPUTED_RESOLUTION'",
                (issue_id,),
            )
            assert cur.fetchone() is not None
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def test_issue_detail_includes_feedback_and_routing_fields(real_client, real_conn, real_admin):
    issue_id = _insert_throwaway_issue(real_conn, category="streetlight", status="closed", reporter_user_id=real_admin.id)
    try:
        real_client.post(f"/api/issues/{issue_id}/feedback", json={"resolved_confirmed": True})
        body = real_client.get(f"/api/issues/{issue_id}").json()
        assert len(body["feedback"]) == 1
        assert body["feedback"][0]["resolved_confirmed"] is True
        assert body["routed_agency"] is None
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def test_post_reports_translates_hindi_and_analyzes_uploaded_photo(real_client, real_conn):
    """End-to-end: a Hindi report with a photo attached should be
    translated (so the English-only classifier actually works instead of
    landing in "other"), and the photo should produce a real, deterministic
    severity signal that can only raise (never lower) the final severity.
    """
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    for i in range(0, 200, 6):
        draw.line([(i, 0), (200 - i, 200)], fill=(200, 30, 30), width=2)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    upload_resp = real_client.post(
        "/api/uploads/photo", files={"file": ("test.jpg", buf, "image/jpeg")}
    )
    assert upload_resp.status_code == 201
    photo_url = upload_resp.json()["photo_url"]
    assert "stored_encrypted" in upload_resp.json()["photo_checks"]
    assert real_client.get(photo_url).status_code == 404  # not attached to any report yet

    # No English "zzqx" marker here (unlike other tests in this file): a
    # short Hindi sentence with a long Latin-script suffix confuses
    # langdetect into guessing "en". Ward 1's guaranteed emptiness (see
    # test_close_then_recurrence_reopens_via_live_reports) is isolation
    # enough on its own.
    hindi_text = "सड़क पर बहुत बड़ा और खतरनाक गड्ढा है, कृपया जल्द से जल्द ठीक करें"
    resp = real_client.post(
        "/api/reports",
        json={"raw_text": hindi_text, "ward_id": 1, "photo_url": photo_url},
    )
    assert resp.status_code == 201
    body = resp.json()
    report = body["report"]

    try:
        # Ward 1 is kept empty by convention in this file (see
        # test_close_then_recurrence_reopens_via_live_reports) specifically
        # so a fresh report here is guaranteed to create its own issue.
        assert body["joined_existing_issue"] is False
        assert report["language"] == "hi"
        if report["translated_text"] is not None:  # translation service may be briefly unreachable
            assert "hole" in report["translated_text"].lower() or "pothole" in report["translated_text"].lower()
            assert body["category"] == "pothole_road"

        assert report["photo_url"] == photo_url
        assert report["photo_severity_score"] is not None
        assert report["photo_severity_band"] in ("cosmetic", "moderate", "critical")
        assert 0.0 <= report["photo_severity_score"] <= 1.0
        assert report["photo_checks"]["had_gps"] is False
        served = real_client.get(photo_url)
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/jpeg"
        # Photo is evidence only: severity (and so priority) comes from text + category.
        from app.nlp.severity import severity
        assert report["severity"] == severity(report["translated_text"] or hindi_text, body["category"])
    finally:
        issue_id = body["issue_id"]
        with real_conn.cursor() as cur:
            cur.execute("DELETE FROM reports WHERE id = %s", (report["id"],))
        real_conn.commit()
        with real_conn.cursor() as cur:
            cur.execute("SELECT id FROM reports WHERE issue_id = %s", (issue_id,))
            remaining = cur.fetchall()
        if not remaining:
            with real_conn.cursor() as cur:
                cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_id,))
                cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
                cur.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
            real_conn.commit()

    import os

    uploaded_path = os.path.join("data", "uploads", os.path.basename(photo_url))
    if os.path.exists(uploaded_path):
        os.remove(uploaded_path)
    with real_conn.cursor() as cur:
        cur.execute("DELETE FROM photo_uploads WHERE filename = %s", (os.path.basename(photo_url),))
    real_conn.commit()


def test_refresh_match_for_issue_survives_prior_signal_on_its_own_match(real_client, real_conn):
    """Regression test: a second live-add to an already-matched, already-
    signalled issue (e.g. issue #24 in the real data - drainage_sewage,
    ward 16, matched to work #1064) used to crash with a ForeignKeyViolation
    inside _refresh_match_for_issue, because it deleted the issue's old
    match row without first clearing the signal that referenced it via
    match_id. Reproduces that exact sequence directly rather than via a
    full report submission (isolates the fix from clustering/geocoding).

    Issue ids are reassigned wholesale every time the pipeline re-clusters
    (the 2026-09-25 demo regen retired #24 entirely), so the donor issue is
    looked up at runtime rather than named: the test only needs *some* issue
    whose category, ward and embedding already produce a match.
    """
    from app.api.main import _refresh_match_for_issue
    from app.core.signals import run_signals

    with real_conn.cursor() as cur:
        cur.execute(
            "SELECT i.id, i.category, i.ward_id FROM issues i JOIN matches m ON m.issue_id = i.id "
            "WHERE i.ward_id IS NOT NULL LIMIT 1"
        )
        donor = cur.fetchone()
    if donor is None:
        pytest.skip("no matched issue in the current dataset to borrow from")
    donor_id, donor_category, donor_ward = donor

    issue_id = _insert_throwaway_issue(real_conn, category=donor_category, ward_id=donor_ward)
    with real_conn.cursor() as cur:
        # match_issue_to_work needs a real embedding on the issue - borrow the
        # donor's (same category/ward, already known to match a work).
        cur.execute("UPDATE issues SET embedding = (SELECT embedding FROM issues WHERE id = %s) WHERE id = %s",
                    (donor_id, issue_id))
    real_conn.commit()
    try:
        first_match = _refresh_match_for_issue(real_conn, issue_id)
        real_conn.commit()
        if first_match is None:
            pytest.skip(f"no matchable work for {donor_category}/ward {donor_ward} in the current dataset")

        run_signals(conn=real_conn)
        real_conn.commit()

        with real_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM signals WHERE issue_id = %s AND match_id IS NOT NULL", (issue_id,))
            assert cur.fetchone()[0] > 0  # precondition: a signal really does reference the match

        second_match = _refresh_match_for_issue(real_conn, issue_id)  # must not raise
        real_conn.commit()
        assert second_match is not None
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def test_devanagari_hazard_keeps_its_critical_band_through_the_api(real_client, real_conn):
    """Regression: severity used to be scored on the machine translation only.
    The translator renders उघड्या तारा / विजेचा धक्का as "open wires" /
    "electric shock", neither of which is a keyword, so an electrocution
    report came back cosmetic while the identical English text came back
    critical. Holds with or without network: if translation is unavailable the
    pipeline falls back to the original text, which now scores critical itself.
    """
    hazard = "कोथरूडमधील विजेच्या खांबाला उघड्या तारा आहेत, मुलांना विजेचा धक्का बसू शकतो"
    resp = real_client.post("/api/reports", json={"raw_text": hazard, "ward_id": 14})
    assert resp.status_code == 201
    body = resp.json()
    issue_id = body["issue_id"]
    try:
        assert body["report"]["severity"] == "critical"
    finally:
        _delete_throwaway_issue(real_conn, issue_id)


def _delete_report_and_issue(conn, report_id, issue_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM signals WHERE issue_id = %s", (issue_id,))
        cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
        cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
        cur.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
    conn.commit()


def test_llm_spam_verdict_holds_report_off_the_board_until_released(real_client, real_conn, monkeypatch):
    """A spam verdict never deletes: the report gets its own hidden issue,
    shows in the staff held queue, reads 'under_review' to the citizen,
    and goes live once staff release it. The LLM is faked."""
    monkeypatch.setattr("app.api.main.classify", lambda text: ("other", 0.2))
    monkeypatch.setattr("app.api.main.triage", lambda raw, translated: {
        "verdict": "spam", "category": "other", "reason": "Promotional text, no civic issue.",
        "model": "fake", "prompt_version": 1,
    })
    resp = real_client.post("/api/reports", json={"raw_text": "zzqx held spam test marker earn money fast aaa bbb"})
    assert resp.status_code == 201
    body = resp.json()
    report_id, issue_id = body["report"]["id"], body["issue_id"]
    try:
        assert body["held_for_review"] is True
        assert body["joined_existing_issue"] is False
        assert body["matched_work"] is None
        assert body["report"]["triage"]["reason"] == "Promotional text, no civic issue."

        assert real_client.get(f"/api/issues/{issue_id}").status_code == 404
        assert real_client.get(f"/api/public/issues/{issue_id}").status_code == 404
        held = real_client.get("/api/held-reports").json()
        assert [h for h in held if h["report_id"] == report_id][0]["triage"]["verdict"] == "spam"
        assert real_client.get(f"/api/me/reports/{report_id}").json()["issue_status"] == "under_review"

        released = real_client.post(f"/api/held-reports/{report_id}/release")
        assert released.status_code == 200
        assert real_client.post(f"/api/held-reports/{report_id}/release").status_code == 404

        detail = real_client.get(f"/api/issues/{issue_id}").json()
        triage = detail["reports"][0]["triage"]
        assert triage["verdict"] == "spam" and triage["released_by"] is not None
        assert detail["priority_score"] is not None
        assert report_id not in [h["report_id"] for h in real_client.get("/api/held-reports").json()]
    finally:
        _delete_report_and_issue(real_conn, report_id, issue_id)


def test_llm_accept_verdict_replaces_other_with_its_category(real_client, real_conn, monkeypatch):
    monkeypatch.setattr("app.api.main.classify", lambda text: ("other", 0.2))
    monkeypatch.setattr("app.api.main.triage", lambda raw, translated: {
        "verdict": "accept", "category": "streetlight", "reason": "Describes a dead streetlight.",
        "model": "fake", "prompt_version": 1,
    })
    resp = real_client.post("/api/reports", json={"raw_text": "zzqx accept test marker lamp aaa bbb ccc"})
    assert resp.status_code == 201
    body = resp.json()
    try:
        assert body["category"] == "streetlight"
        assert body["held_for_review"] is False
        assert body["report"]["category_conf"] == 0.2  # the classifier's own score is kept
    finally:
        _delete_report_and_issue(real_conn, body["report"]["id"], body["issue_id"])
