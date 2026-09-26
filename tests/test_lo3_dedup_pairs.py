from datetime import datetime, timedelta, timezone

from scripts.lo3.dedup_pairs import pair_type, select_examples

BASE = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _report(report_id, category="drainage_sewage", ward_id=31, days=0):
    return {
        "id": report_id, "category": category, "ward_id": ward_id,
        "geom_confidence": 0.4, "lat": 18.5, "lon": 73.8,
        "reported_at": BASE + timedelta(days=days),
        "text": f"report {report_id}", "locality": "somewhere",
    }


def test_same_ward_same_category_in_window_above_threshold_is_likely_duplicate():
    assert pair_type(_report(1), _report(2, days=3), sim=0.91, days_apart=3) == "likely_duplicate"


def test_similarity_just_below_threshold_is_flagged_as_the_boundary_case():
    # The band the human labels exist to re-tune - see clustering.COSINE_THRESHOLD.
    assert pair_type(_report(1), _report(2), sim=0.74, days_apart=1) == "boundary_below_threshold"


def test_gated_pair_with_low_similarity_is_offered_without_prejudging_it():
    assert pair_type(_report(1), _report(2), sim=0.52, days_apart=1) == "gated_low_similarity"


def test_trivially_dissimilar_pairs_are_not_offered_for_review():
    assert pair_type(_report(1), _report(2), sim=0.10, days_apart=1) is None


def test_high_similarity_outside_the_time_window_is_kept_as_a_gate_check():
    assert pair_type(_report(1), _report(2, days=40), sim=0.93, days_apart=40) == "outside_time_window"


def test_high_similarity_across_wards_is_kept_as_a_spatial_gate_check():
    pair = pair_type(_report(1), _report(2, ward_id=14), sim=0.93, days_apart=2)
    assert pair == "different_ward_high_similarity"


def test_different_categories_at_one_place_and_time_surface_as_category_error_candidates():
    pair = pair_type(_report(1), _report(2, category="water_supply"), sim=0.68, days_apart=2)
    assert pair == "cross_category_same_place_time"


def test_different_categories_that_are_also_dissimilar_are_dropped():
    assert pair_type(_report(1), _report(2, category="streetlight"), sim=0.20, days_apart=2) is None


def test_selection_never_reuses_a_report_across_pairs():
    candidates = [
        ("likely_duplicate", _report(1), _report(2), 0.91, 1),
        ("likely_duplicate", _report(1), _report(3), 0.90, 1),  # report 1 already used
        ("likely_duplicate", _report(3), _report(4), 0.89, 1),
    ]
    picked = select_examples(candidates, quota={"likely_duplicate": 10}, max_examples=10)
    used = [r["id"] for _, a, b, _, _ in picked for r in (a, b)]
    assert len(used) == len(set(used))
    assert [(a["id"], b["id"]) for _, a, b, _, _ in picked] == [(1, 2), (3, 4)]


def test_selection_respects_per_bucket_quota_and_overall_cap():
    candidates = [("likely_duplicate", _report(i), _report(i + 100), 0.9, 1) for i in range(1, 6)]
    assert len(select_examples(candidates, quota={"likely_duplicate": 2}, max_examples=10)) == 2
    assert len(select_examples(candidates, quota={"likely_duplicate": 9}, max_examples=3)) == 3
