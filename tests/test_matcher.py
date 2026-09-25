from datetime import date, datetime, timedelta

import numpy as np

from app.core.matcher import match_issue_to_work, run_matcher

SIMILAR_A = [1.0, 0.0] + [0.0] * 382
SIMILAR_B = [0.99, 0.14] + [0.0] * 382  # cosine ~0.99 with SIMILAR_A
DIFFERENT = [0.0, 1.0] + [0.0] * 382  # cosine 0.0 with SIMILAR_A


def _vec_literal(values):
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def _insert_work(conn, category, status, completed_on, lat, lon, ward_id, description,
                  embedding=SIMILAR_A, geom_confidence=1.0):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO works (work_name, description, category, status, completed_on, geom, ward_id,
                               geom_confidence, embedding)
            VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s::vector)
            RETURNING id
            """,
            ("test work", description, category, status, completed_on, lon, lat, ward_id,
             geom_confidence, _vec_literal(embedding)),
        )
        return cur.fetchone()[0]


def _insert_issue(conn, category, ward_id, lat, lon, last_reported, embedding=SIMILAR_A,
                   report_confidences=(1.0,)):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO issues (category, ward_id, status, geom, last_reported, first_reported, embedding)
            VALUES (%s, %s, 'open', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s::vector)
            RETURNING id
            """,
            (category, ward_id, lon, lat, last_reported, last_reported, _vec_literal(embedding)),
        )
        issue_id = cur.fetchone()[0]
        for conf in report_confidences:
            cur.execute(
                "INSERT INTO reports (raw_text, reported_at, category, issue_id, geom_confidence, is_synthetic) "
                "VALUES ('r', %s, %s, %s, %s, true)",
                (last_reported, category, issue_id, conf),
            )
    return issue_id


NOW = datetime(2026, 9, 20)


def test_precise_close_match_reports_real_distance(db_conn):
    # Both sides precise (work geocoded from a landmark, geom_confidence 1.0).
    work_id = _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                            18.55, 73.85, 11, "Drain work near Some Landmark")
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.5501, 73.8501, NOW,
                              report_confidences=(1.0, 1.0))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is not None
    assert match["work_id"] == work_id
    assert match["distance_m"] is not None
    assert match["distance_m"] < 100
    assert "ward-level" not in match["match_reason"].lower()


def test_ward_level_match_never_fabricates_distance(db_conn):
    work_id = _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                            18.55, 73.85, 11, "Drainage Line at Ward No.11", geom_confidence=0.5)
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.9, 74.3, NOW,
                              report_confidences=(0.4, 0.4))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is not None
    assert match["work_id"] == work_id
    assert match["distance_m"] is None
    assert "ward" in match["match_reason"].lower()


def test_ward_level_requires_same_ward_not_just_any_distance(db_conn):
    _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                 18.55, 73.85, 11, "Drainage Line at Ward No.11", geom_confidence=0.5)
    issue_id = _insert_issue(db_conn, "drainage_sewage", 12, 18.55, 73.85, NOW,
                              report_confidences=(0.4,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is None


def test_other_category_never_matches_even_if_everything_else_lines_up(db_conn):
    # Regression: found in the real 400-report run - an 'other'-category
    # issue matched an 'other'-category work purely because both landed in
    # the catch-all bucket. 'other' means "no real category on either
    # side", so that pairing is noise, not a discovered link.
    _insert_work(db_conn, "other", "completed", date(2026, 3, 1),
                 18.55, 73.85, 11, "Concreting near a toilet block")
    issue_id = _insert_issue(db_conn, "other", 11, 18.5501, 73.8501, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "other"}, db_conn)
    assert match is None


def test_different_category_never_matches(db_conn):
    _insert_work(db_conn, "pothole_road", "completed", date(2026, 3, 1),
                 18.55, 73.85, 11, "Road work near Landmark")
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.55, 73.85, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is None


def test_recommended_not_completed_work_is_not_a_candidate(db_conn):
    _insert_work(db_conn, "drainage_sewage", "recommended", None,
                 18.55, 73.85, 11, "Drainage Line near Landmark")
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.55, 73.85, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is None


def test_work_completed_after_issue_last_report_is_not_a_candidate(db_conn):
    _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 9, 25),  # after NOW
                 18.55, 73.85, 11, "Drainage Line near Landmark")
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.55, 73.85, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is None


def test_completion_too_long_ago_is_not_a_candidate(db_conn):
    _insert_work(db_conn, "drainage_sewage", "completed", date(2015, 1, 1),  # >10 years ago
                 18.55, 73.85, 11, "Drainage Line near Landmark")
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.55, 73.85, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is None


def test_low_semantic_similarity_is_not_a_candidate(db_conn):
    _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                 18.55, 73.85, 11, "Drainage Line near Landmark", embedding=DIFFERENT)
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.55, 73.85, NOW,
                              embedding=SIMILAR_A, report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is None


def test_picks_top_scoring_candidate_among_several(db_conn):
    far_work_id = _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                                18.5510, 73.8510, 11, "Drainage far near Landmark")  # ~140m away
    close_work_id = _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                                  18.5501, 73.8501, 11, "Drainage close near Landmark")  # ~14m away
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.5500, 73.8500, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert match is not None
    assert match["work_id"] == close_work_id
    assert match["work_id"] != far_work_id


def test_match_reason_names_both_record_ids(db_conn):
    work_id = _insert_work(db_conn, "drainage_sewage", "completed", date(2026, 3, 1),
                            18.55, 73.85, 11, "Drainage work near Landmark")
    issue_id = _insert_issue(db_conn, "drainage_sewage", 11, 18.5501, 73.8501, NOW,
                              report_confidences=(1.0,))

    match = match_issue_to_work({"id": issue_id, "category": "drainage_sewage"}, db_conn)
    assert str(issue_id) in match["match_reason"]
    assert str(work_id) in match["match_reason"]


def test_run_matcher_writes_matches_table(clean_reports, clean_works):
    with clean_reports.cursor() as cur:
        cur.execute("DELETE FROM matches")
        cur.execute("DELETE FROM issues")

    work_id = _insert_work(clean_works, "drainage_sewage", "completed", date(2026, 3, 1),
                            18.55, 73.85, 11, "Drainage work near Landmark")
    issue_id = _insert_issue(clean_reports, "drainage_sewage", 11, 18.5501, 73.8501, NOW,
                              report_confidences=(1.0,))

    matches = run_matcher(conn=clean_reports)
    assert len(matches) == 1
    assert matches[0]["issue_id"] == issue_id
    assert matches[0]["work_id"] == work_id

    with clean_reports.cursor() as cur:
        cur.execute("SELECT issue_id, work_id, semantic_score, combined_score FROM matches")
        row = cur.fetchone()
        assert row[0] == issue_id
        assert row[1] == work_id
        assert row[2] > 0
        assert row[3] > 0
