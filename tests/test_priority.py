from datetime import datetime, timedelta

from app.core.priority import (
    SEVERITY_SCORE,
    W_EXPOSURE,
    W_RECURRENCE,
    W_SEVERITY,
    W_TIME_OPEN,
    _exposure_radius,
    _site_weight,
    compute_exposure,
    compute_priority,
    run_priority,
)

NOW = datetime(2026, 9, 20)
SIMILAR_A = "[" + ",".join(["1.0", "0.0"] + ["0.0"] * 382) + "]"


def _insert_issue(conn, category, ward_id, lat, lon, first_reported, recurrence_count=0,
                   closed_at=None, status="open"):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO issues (category, ward_id, status, geom, first_reported, last_reported,
                                 recurrence_count, closed_at, embedding, report_count)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s::vector, 1)
            RETURNING id
            """,
            (category, ward_id, status, lon, lat, first_reported, first_reported,
             recurrence_count, closed_at, SIMILAR_A),
        )
        return cur.fetchone()[0]


def _insert_report(conn, issue_id, category, severity, geom_confidence=1.0, lat=18.55, lon=73.85):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO reports (raw_text, reported_at, category, severity, issue_id, geom_confidence, geom, is_synthetic) "
            "VALUES ('r', now(), %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s,%s),4326), true)",
            (category, severity, issue_id, geom_confidence, lon, lat),
        )


def _insert_site(conn, kind, lat, lon, name="Test Site", source_id=None):
    import uuid
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sensitive_sites (name, kind, geom, source_id) VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s,%s),4326), %s)",
            (name, kind, lon, lat, source_id or f"test/{uuid.uuid4()}"),
        )


def test_weights_sum_to_one():
    assert abs((W_EXPOSURE + W_SEVERITY + W_RECURRENCE + W_TIME_OPEN) - 1.0) < 1e-9


def test_severity_score_is_normalized_0_to_1():
    assert SEVERITY_SCORE["cosmetic"] == 0.0
    assert SEVERITY_SCORE["critical"] == 1.0
    assert 0.0 < SEVERITY_SCORE["moderate"] < 1.0


def test_site_weight_school_and_hospital_are_1():
    assert _site_weight("school", "pothole_road") == 1.0
    assert _site_weight("hospital", "pothole_road") == 1.0


def test_site_weight_market_is_0_7():
    assert _site_weight("market", "pothole_road") == 0.7


def test_site_weight_bus_stop_is_0_5():
    assert _site_weight("bus_stop", "pothole_road") == 0.5


def test_site_weight_water_body_default_is_0_6():
    assert _site_weight("water_body", "pothole_road") == 0.6


def test_site_weight_water_body_elevated_for_drainage_category():
    assert _site_weight("water_body", "drainage_sewage") > 0.6


def test_exposure_radius_falls_back_to_base_when_no_density_data(db_conn):
    # Establish the precondition instead of assuming it: area_sqkm is filled
    # for every ward now (load_wards derives it from the geometry), and the
    # ward tests commit a population, so "no density data" has to be set up.
    with db_conn.cursor() as cur:
        cur.execute("UPDATE wards SET population = NULL WHERE id = 1")
    radius = _exposure_radius(db_conn, ward_id=1)
    from app.core.priority import BASE_EXPOSURE_RADIUS_M
    assert radius == BASE_EXPOSURE_RADIUS_M


def test_exposure_radius_scales_with_density_when_data_present(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("UPDATE wards SET population = 50000, area_sqkm = 1.0 WHERE id = 1")  # very dense
    dense_radius = _exposure_radius(db_conn, ward_id=1)
    with db_conn.cursor() as cur:
        cur.execute("UPDATE wards SET population = 5000, area_sqkm = 10.0 WHERE id = 1")  # sparse
    sparse_radius = _exposure_radius(db_conn, ward_id=1)
    assert dense_radius < sparse_radius


def test_compute_exposure_finds_precise_nearby_school(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sensitive_sites")
    _insert_site(db_conn, "school", 18.5501, 73.8501)  # ~14m from issue below
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", geom_confidence=1.0, lat=18.5500, lon=73.8500)

    score, detail = compute_exposure({"id": issue_id, "category": "pothole_road", "ward_id": 11,
                                       "lat": 18.5500, "lon": 73.8500}, db_conn)
    assert score == 1.0
    assert detail["spatial_basis"] == "precise"
    assert detail["matched_site"]["kind"] == "school"
    assert detail["matched_site"]["distance_m"] is not None


def test_compute_exposure_ward_level_never_reports_fake_distance(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sensitive_sites")
    _insert_site(db_conn, "hospital", 18.556, 73.831)  # somewhere in ward 11
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", geom_confidence=0.4, lat=18.5500, lon=73.8500)

    score, detail = compute_exposure({"id": issue_id, "category": "pothole_road", "ward_id": 11,
                                       "lat": 18.5500, "lon": 73.8500}, db_conn)
    assert score == 1.0
    assert detail["spatial_basis"] == "ward"
    assert detail["matched_site"]["distance_m"] is None
    assert detail["radius_m"] is None  # a radius wasn't meaningfully applied - ward membership was


def test_compute_exposure_returns_zero_when_no_sites_nearby(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sensitive_sites")
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", geom_confidence=1.0, lat=18.5500, lon=73.8500)

    score, detail = compute_exposure({"id": issue_id, "category": "pothole_road", "ward_id": 11,
                                       "lat": 18.5500, "lon": 73.8500}, db_conn)
    assert score == 0.0
    assert detail["matched_site"] is None


def test_compute_exposure_uses_max_not_sum(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sensitive_sites")
    for _ in range(5):
        _insert_site(db_conn, "bus_stop", 18.5501, 73.8501)
    _insert_site(db_conn, "hospital", 18.5502, 73.8502)
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", geom_confidence=1.0, lat=18.5500, lon=73.8500)

    score, detail = compute_exposure({"id": issue_id, "category": "pothole_road", "ward_id": 11,
                                       "lat": 18.5500, "lon": 73.8500}, db_conn)
    assert score == 1.0  # hospital wins even though 5 bus stops are also nearby
    assert detail["matched_site"]["kind"] == "hospital"


def test_compute_priority_severity_term_reflects_worst_member_report(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sensitive_sites")
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(db_conn, issue_id, "pothole_road", "cosmetic", lat=18.5500, lon=73.8500)
    _insert_report(db_conn, issue_id, "pothole_road", "critical", lat=18.5500, lon=73.8500)

    total, breakdown = compute_priority(issue_id, db_conn)
    assert breakdown["severity_band"] == "critical"
    assert breakdown["terms"]["severity"] == 1.0


def test_compute_priority_recurrence_zero_when_never_recurred(db_conn):
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW, recurrence_count=0)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", lat=18.5500, lon=73.8500)

    total, breakdown = compute_priority(issue_id, db_conn)
    assert breakdown["terms"]["recurrence"] == 0.0


def test_compute_priority_recurrence_term_scales_with_count(db_conn):
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW, recurrence_count=2)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", lat=18.5500, lon=73.8500)

    total, breakdown = compute_priority(issue_id, db_conn)
    assert 0.0 < breakdown["terms"]["recurrence"] <= 1.0


def test_compute_priority_time_open_scales_with_age(db_conn):
    old_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW - timedelta(days=200))
    _insert_report(db_conn, old_id, "pothole_road", "moderate", lat=18.5500, lon=73.8500)
    new_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW - timedelta(days=1))
    _insert_report(db_conn, new_id, "pothole_road", "moderate", lat=18.5500, lon=73.8500)

    _, old_breakdown = compute_priority(old_id, db_conn)
    _, new_breakdown = compute_priority(new_id, db_conn)
    assert old_breakdown["terms"]["time_open"] > new_breakdown["terms"]["time_open"]
    assert old_breakdown["terms"]["time_open"] == 1.0  # capped at the normalization ceiling


def test_compute_priority_full_breakdown_has_all_required_fields(db_conn):
    issue_id = _insert_issue(db_conn, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(db_conn, issue_id, "pothole_road", "moderate", lat=18.5500, lon=73.8500)

    total, breakdown = compute_priority(issue_id, db_conn)
    assert isinstance(total, float)
    assert set(breakdown["terms"]) == {"exposure", "severity", "recurrence", "time_open"}
    assert set(breakdown["weights"]) == {"exposure", "severity", "recurrence", "time_open"}
    assert "explanation" in breakdown
    assert isinstance(breakdown["explanation"], str)


def test_run_priority_writes_scores_to_issues_table(clean_reports, clean_works):
    with clean_reports.cursor() as cur:
        cur.execute("DELETE FROM issues")
    issue_id = _insert_issue(clean_reports, "pothole_road", 11, 18.5500, 73.8500, NOW)
    _insert_report(clean_reports, issue_id, "pothole_road", "moderate", lat=18.5500, lon=73.8500)

    count = run_priority(conn=clean_reports)
    assert count == 1

    with clean_reports.cursor() as cur:
        cur.execute("SELECT priority_score, priority_breakdown FROM issues WHERE id = %s", (issue_id,))
        score, breakdown = cur.fetchone()
    assert score is not None
    assert breakdown is not None
    assert "terms" in breakdown
