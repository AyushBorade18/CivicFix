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
    assert pair_type(_report(1), _report(2), sim=0.38, days_apart=1) == "gated_low_similarity"


def test_the_boundary_band_reaches_down_to_where_the_real_mass_is():
    # Measured: the decision mass sits at 0.50-0.80, and [0.65,0.70) is a
    # sparse dip. 0.52 must be a boundary case, not a written-off negative.
    assert pair_type(_report(1), _report(2), sim=0.52, days_apart=1) == "boundary_below_threshold"


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


def test_selection_caps_how_often_one_wording_is_reused():
    # Report 1 is paired with 2,3,4,5; with a cap of 2 it may appear twice.
    candidates = [("likely_duplicate", _report(1), _report(n), 0.9, 1) for n in (2, 3, 4, 5)]
    picked = select_examples(candidates, quota={"likely_duplicate": 10},
                             max_examples=10, max_text_uses=2)
    assert len(picked) == 2
    assert [(a["id"], b["id"]) for _, a, b, _, _ in picked] == [(1, 2), (1, 3)]


def test_the_reuse_cap_counts_wording_not_report_id():
    # The synthetic corpus repeats templates verbatim under different ids, so
    # an id-based cap would let one sentence reach a reviewer many times.
    shared = [_report(n) for n in (1, 2, 3, 4)]
    for r in shared:
        r["text"] = "same wording under four different ids"
    partners = [_report(n + 100) for n in range(4)]
    candidates = [("likely_duplicate", shared[i], partners[i], 0.9, 1) for i in range(4)]
    picked = select_examples(candidates, quota={"likely_duplicate": 10},
                             max_examples=10, max_text_uses=2)
    assert len(picked) == 2


def test_selection_never_offers_the_same_text_pair_twice():
    a, b = _report(1), _report(2)
    duplicate_of_a = _report(9)
    duplicate_of_a["text"] = a["text"]  # different row, same wording
    candidates = [
        ("likely_duplicate", a, b, 0.91, 1),
        ("likely_duplicate", duplicate_of_a, b, 0.90, 1),
    ]
    picked = select_examples(candidates, quota={"likely_duplicate": 10}, max_examples=10)
    assert len(picked) == 1


def test_selection_respects_per_bucket_quota_and_overall_cap():
    candidates = [("likely_duplicate", _report(i), _report(i + 100), 0.9, 1) for i in range(1, 6)]
    assert len(select_examples(candidates, quota={"likely_duplicate": 2}, max_examples=10)) == 2
    assert len(select_examples(candidates, quota={"likely_duplicate": 9}, max_examples=3)) == 3
