from scripts.eval.gold_eval import (
    best_threshold,
    dedup_eval,
    gold_dedup_pairs,
    load_gold,
    script_of,
    severity_eval,
    threshold_sweep,
)


def _row(gold_id, category="drainage_sewage", severity="moderate", dup_group="", text="x",
         split="test"):
    return {"gold_id": gold_id, "split": split, "text": text, "category": category,
            "severity": severity, "dup_group": dup_group}


def test_script_detection_separates_devanagari_from_latin():
    assert script_of("Drainage chamber overflowing since 4 days") == "latin"
    assert script_of("गटार तुंबले आहे") == "devanagari"
    # Romanized Marathi/Hindi is Latin script - that is the point of the split:
    # it looks English to a script check but is not English.
    assert script_of("kelewadi mein gutter ka paani road pe aa raha hai") == "latin"


def test_severity_eval_scores_against_the_gold_band():
    rows = [
        _row("G1", category="streetlight", severity="critical",
             text="exposed wires here, electrocution risk"),
        _row("G2", category="streetlight", severity="cosmetic",
             text="streetlight flickering occasionally"),
    ]
    result = severity_eval(rows)
    assert result["n"] == 2
    assert result["correct"] == 2
    assert result["accuracy"] == 1.0


def test_severity_eval_reports_the_misses_so_they_can_be_read():
    rows = [_row("G9", category="footpath", severity="critical", text="tiles are a bit uneven")]
    result = severity_eval(rows)
    assert result["accuracy"] == 0.0
    assert result["misses"] == [{"gold_id": "G9", "expected": "critical", "got": "moderate"}]


def test_gold_dedup_pairs_labels_same_group_as_duplicate():
    rows = [_row("G1", dup_group="D01"), _row("G2", dup_group="D01"), _row("G3", dup_group="D02")]
    pairs = gold_dedup_pairs(rows)
    labels = {(a["gold_id"], b["gold_id"]): dup for a, b, dup in pairs}
    assert labels[("G1", "G2")] is True
    assert labels[("G1", "G3")] is False


def test_gold_dedup_pairs_only_compares_within_a_category():
    # The clusterer groups by category first, so a cross-category pair is never
    # a candidate and must not be counted as a miss.
    rows = [_row("G1", category="footpath", dup_group="D01"),
            _row("G2", category="drainage_sewage", dup_group="D01")]
    assert gold_dedup_pairs(rows) == []


def test_gold_dedup_pairs_ignores_rows_with_no_group():
    rows = [_row("G1", dup_group=""), _row("G2", dup_group="")]
    assert gold_dedup_pairs(rows) == []


def test_dedup_eval_computes_precision_recall_from_similarities():
    # (pair_is_duplicate, similarity) at threshold 0.8:
    #   TP 0.9 dup, FN 0.7 dup, FP 0.85 non-dup, TN 0.2 non-dup
    scored = [(True, 0.9), (True, 0.7), (False, 0.85), (False, 0.2)]
    result = dedup_eval(scored, threshold=0.8)
    assert (result["true_positives"], result["false_negatives"]) == (1, 1)
    assert (result["false_positives"], result["true_negatives"]) == (1, 1)
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_dedup_eval_handles_a_threshold_nothing_reaches():
    scored = [(True, 0.5), (False, 0.1)]
    result = dedup_eval(scored, threshold=0.99)
    assert result["true_positives"] == 0
    assert result["precision"] is None  # nothing predicted duplicate - not 0.0
    assert result["recall"] == 0.0


def test_threshold_sweep_reports_every_candidate():
    scored = [(True, 0.90), (True, 0.72), (False, 0.40), (False, 0.35)]
    sweep = threshold_sweep(scored, candidates=[0.5, 0.7, 0.95])
    assert [s["threshold"] for s in sweep] == [0.5, 0.7, 0.95]


def test_best_threshold_breaks_an_f1_tie_toward_the_higher_threshold():
    # 0.5 and 0.7 both catch both duplicates with no false positives, so both
    # score f1 1.0. The higher one must win: a wrong merge is worse than a
    # missed one, so ties resolve to the conservative end.
    scored = [(True, 0.90), (True, 0.72), (False, 0.40), (False, 0.35)]
    sweep = threshold_sweep(scored, candidates=[0.5, 0.7, 0.95])
    best = best_threshold(sweep)
    assert best["f1"] == 1.0
    assert best["threshold"] == 0.7


def test_best_threshold_is_none_when_no_threshold_scores_at_all():
    assert best_threshold(threshold_sweep([(False, 0.1)], candidates=[0.5])) is None


def test_load_gold_reads_the_real_sheet():
    rows = load_gold()
    assert len(rows) == 64
    assert {r["split"] for r in rows} == {"seed", "test"}


def test_severity_eval_separates_dangerous_misses_from_harmless_ones():
    rows = [
        # gold critical, scored lower -> dangerous
        _row("G1", category="streetlight", severity="critical", text="bulb is dim"),
        # gold cosmetic, scored higher -> over-call, not dangerous
        _row("G2", category="drainage_sewage", severity="cosmetic", text="drain needs a look"),
    ]
    result = severity_eval(rows)
    assert result["under_calls"] == 1
    assert result["over_calls"] == 1
    assert result["dangerous_misses"] == 1
    assert result["dangerous_miss_detail"][0]["gold_id"] == "G1"


def test_critical_recall_is_reported_against_gold_criticals_only():
    rows = [
        # "electrocution" is a long-standing keyword, so this one is caught -
        # the test is about the metric, not about which words are in the list.
        _row("G1", category="streetlight", severity="critical",
             text="exposed wires, electrocution risk"),
        _row("G2", category="streetlight", severity="critical", text="bulb is dim"),
        _row("G3", category="footpath", severity="cosmetic", text="slightly worn paint"),
    ]
    result = severity_eval(rows)
    assert result["n_gold_critical"] == 2
    assert result["critical_recall"] == 0.5  # one of the two criticals caught
