import numpy as np

from app.categories import CIVIC_CATEGORIES
from training.train_classifier import load_all_sources, sample_weights, split_rows, threshold_table


def test_sources_load_with_labels_languages_and_source_tags():
    rows = load_all_sources()
    assert {r["source"] for r in rows} >= {"icmyc_bengaluru", "synthetic_complaints", "synthetic_groups"}
    assert all(r["category"] in CIVIC_CATEGORIES for r in rows)
    assert all(r["text"].strip() and r["language"] for r in rows)
    assert {r["language"] for r in rows if r["source"] == "icmyc_bengaluru"} == {"english"}


def test_split_keeps_paraphrase_groups_whole_and_is_deterministic():
    rows = load_all_sources()
    train, test = split_rows(rows)
    train_groups = {r["group_id"] for r in train if r["group_id"]}
    test_groups = {r["group_id"] for r in test if r["group_id"]}
    assert train_groups.isdisjoint(test_groups)
    assert {r["source"] for r in test} == {r["source"] for r in rows}
    assert [r["text"] for r in split_rows(rows)[1]] == [r["text"] for r in test]


def test_weights_give_real_and_synthetic_data_equal_total_and_balance_categories():
    rows = ([{"category": "pothole_road", "source": "icmyc_bengaluru"}] * 90
            + [{"category": "other", "source": "icmyc_bengaluru"}] * 10
            + [{"category": "pothole_road", "source": "synthetic_complaints"}] * 5
            + [{"category": "other", "source": "synthetic_groups"}] * 5)
    w = sample_weights(rows)
    real = sum(w[i] for i, r in enumerate(rows) if r["source"] == "icmyc_bengaluru")
    synth = sum(w) - real
    assert abs(real - synth) < 1e-6
    real_pothole = sum(w[i] for i in range(90))
    real_other = sum(w[i] for i in range(90, 100))
    assert abs(real_pothole - real_other) < 1e-6


def test_threshold_table_reports_coverage_and_accuracy_above_each_cutoff():
    confidences = np.array([0.9, 0.8, 0.4, 0.3])
    correct = np.array([True, False, True, False])
    table = threshold_table(confidences, correct, thresholds=(0.5,))
    assert table == [{"threshold": 0.5, "coverage": 0.5, "accuracy": 0.5}]
