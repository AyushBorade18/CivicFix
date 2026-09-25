from app.ingest.synthetic import (
    _anchor_location_cue,
    _pick_reported_at,
    fetch_anchors,
    generate_synthetic_reports,
    render_complaint,
)
import random
from datetime import datetime, timedelta


def test_anchor_location_cue_uses_the_works_resolved_2022_ward():
    cue = _anchor_location_cue("Road Concreting at Ward No.11, Sutardara Kothrud.", ward_id=30)
    assert cue == "Ward 30"


def test_anchor_location_cue_never_uses_the_raw_mplads_ward_number():
    # MPLADS ward numbers mix old/new/PCMC schemes; "Ward 11" in the text is
    # not 2022 ward 11 (see app/ingest/mplads.py).
    cue = _anchor_location_cue("Road Concreting at Ward No.11, Sutardara Kothrud.")
    assert cue != "Ward 11"


def test_anchor_location_cue_uses_landmark_when_no_ward_number():
    cue = _anchor_location_cue("Development of footpath at Dasara Chowk, Balewadi.")
    assert cue == "Dasara Chowk"


def test_render_complaint_fills_placeholder():
    text = render_complaint("Pothole near {landmark}, please fix", "Ward 11")
    assert text == "Pothole near Ward 11, please fix"


def test_pick_reported_at_within_range():
    rng = random.Random(1)
    now = datetime(2026, 9, 20)
    dt = _pick_reported_at(rng, now=now, days_back=120)
    assert now - timedelta(days=120) <= dt <= now


def test_fetch_anchors_only_returns_matchable_works(db_conn):
    # Matchable = what app/core/matcher.py can link: completed, dated, located, not 'other'.
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE works CASCADE")
        cur.execute(
            """
            INSERT INTO works (work_name, description, category, geom, ward_id, status, completed_on)
            VALUES
            ('Drain work', 'Laying Of Drainage Line at Ward No.13', 'drainage_sewage',
             ST_SetSRID(ST_MakePoint(73.78, 18.56), 4326), 13, 'completed', '2026-01-10'),
            ('Unrelated hall', 'Construction of a hall', 'other',
             ST_SetSRID(ST_MakePoint(73.79, 18.57), 4326), 13, 'completed', '2026-01-10'),
            ('Unresolved pothole work', 'Pothole repair somewhere', 'pothole_road', NULL, NULL,
             'completed', '2026-01-10'),
            ('Unfinished drain', 'Drainage line at Dasara Chowk', 'drainage_sewage',
             ST_SetSRID(ST_MakePoint(73.77, 18.57), 4326), 12, 'sanctioned', NULL),
            ('PCMC road', 'Construct a Road At Thergaon near Mini Market', 'pothole_road',
             ST_SetSRID(ST_MakePoint(73.76, 18.61), 4326), NULL, 'completed', '2026-01-10')
            """
        )
    db_conn.commit()

    anchors = fetch_anchors(db_conn)
    assert len(anchors) == 1
    assert anchors[0]["category"] == "drainage_sewage"
    assert anchors[0]["ward_id"] == 13
    assert anchors[0]["cue"] == "Ward 13"


def test_generate_synthetic_reports_end_to_end(clean_reports, clean_works):
    with clean_works.cursor() as cur:
        cur.execute(
            """
            INSERT INTO works (work_name, description, category, geom, ward_id, status, completed_on)
            VALUES
            ('Drain work', 'Laying Of Drainage Line at Ward No.13', 'drainage_sewage',
             ST_SetSRID(ST_MakePoint(73.78, 18.56), 4326), 13, 'completed', '2026-01-10'),
            ('Footpath work', 'Development of footpath at Dasara Chowk, Balewadi.', 'footpath',
             ST_SetSRID(ST_MakePoint(73.7761167, 18.5737452), 4326), 12, 'completed', '2026-02-01')
            """
        )
    clean_works.commit()

    inserted = generate_synthetic_reports(n=30, seed=7, conn=clean_reports)

    assert inserted == 30
    with clean_reports.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        assert cur.fetchone()[0] == 30

        cur.execute("SELECT count(*) FROM reports WHERE is_synthetic = false")
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM reports WHERE embedding IS NOT NULL")
        assert cur.fetchone()[0] == 30

        cur.execute("SELECT count(DISTINCT category) FROM reports")
        assert cur.fetchone()[0] > 1

        cur.execute("SELECT count(*) FROM reports WHERE ward_id IS NOT NULL")
        with_ward = cur.fetchone()[0]
        assert with_ward > 0

        cur.execute("SELECT count(*) FROM reports WHERE geom IS NOT NULL")
        with_geom = cur.fetchone()[0]
        assert with_geom > 0
