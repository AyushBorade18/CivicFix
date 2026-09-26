"""Layer 5: evaluate severity and deduplication against the human gold set.

    python -m scripts.eval.gold_eval

data/labelling/lo2_gold_complaints.csv has been read only for its `category`
column. It also carries two labels nobody has scored against:

  severity   64 human bands (19 critical / 33 moderate / 12 cosmetic)
  dup_group  10 duplicate groups covering 21 complaints - real "these are the
             same issue" ground truth, including cross-lingual pairs (D01 is
             an English complaint and a romanized Hindi one about one drain)

So app/core/metrics.py's note that dedup ground truth "doesn't exist" is out
of date, and severity has never been measured at all.

What this measures, and what it does not: the dedup half scores the TEXT
SIMILARITY decision only - the one thing COSINE_THRESHOLD controls. The
clusterer's distance and time gates are not applied, because gold rows carry a
locality string and a date rather than a resolved geometry, and faking a
geometry to run the full clusterer would measure the fake. Pairs are
restricted to the same category, which is the one gate the sheet does support.
Read the numbers as "how well does the encoder separate duplicates from
non-duplicates", not as end-to-end clustering accuracy.

Leakage: the 42 `seed` rows shaped the synthetic corpus the encoder was
fine-tuned on, so they are not a clean test. Every number is reported for the
22 `test` rows (clean) and for all 64 (leaky, marked as such) - never merged.

Severity is scored using the GOLD category, not the classifier's, so a
classification error is not charged to severity.
"""
import csv
import json
from itertools import combinations
from pathlib import Path

from app.core.clustering import COSINE_THRESHOLD, _cosine_similarity
from app.nlp.embeddings import get_embedding_model
from app.nlp.severity import BAND_ORDER, severity

GOLD_CSV = "data/labelling/lo2_gold_complaints.csv"
OUTPUT_JSON = Path("data/eval/gold_eval.json")
SWEEP = [round(0.40 + 0.025 * i, 3) for i in range(25)]  # 0.400 .. 0.975

# Gold rows whose text was READ while choosing severity keywords, so they can
# never serve as a held-out severity score again. Recorded rather than
# remembered, because the mistake is invisible otherwise: 8 of these sit in the
# `test` split, which made the "clean test split" severity number look like a
# held-out result when it was partly fitted to.
#
# The seed/test split is the right boundary for anything touching the ENCODER
# (dedup), since the 42 seed rows shaped the synthetic fine-tuning corpus.
# severity() never touches the encoder - it is keywords plus priors - so for
# severity the boundary that matters is this list. Append to it whenever a row
# is read while tuning.
TUNED_ON_GOLD_IDS = {
    "G003", "G007", "G017", "G018", "G020", "G022", "G026",
    "G033", "G043", "G050", "G051", "G052", "G055", "G061",
}


def load_gold(path: str = GOLD_CSV) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def script_of(text: str) -> str:
    return "devanagari" if any("ऀ" <= c <= "ॿ" for c in text or "") else "latin"


def severity_eval(rows: list[dict]) -> dict:
    """Accuracy, plus the split that actually matters operationally.

    Over- and under-calls are not equally bad. Under-calling a live wire sends
    a hazard to the back of the queue; over-calling litter just wastes a
    reviewer's attention. `dangerous_misses` counts the worst case on its own -
    a complaint humans called critical that we scored lower - because a single
    accuracy number hides it.
    """
    correct, misses, over, under, dangerous = 0, [], 0, 0, []
    by_script: dict[str, list[int]] = {}
    for row in rows:
        got = severity(row["text"], row["category"])
        expected = row["severity"].strip()
        hit = got == expected
        correct += hit
        if not hit:
            misses.append({"gold_id": row["gold_id"], "expected": expected, "got": got})
            if BAND_ORDER.index(got) > BAND_ORDER.index(expected):
                over += 1
            else:
                under += 1
                if expected == "critical":
                    dangerous.append({"gold_id": row["gold_id"], "got": got,
                                      "text": row["text"][:80]})
        by_script.setdefault(script_of(row["text"]), []).append(int(hit))
    n_critical = sum(1 for r in rows if r["severity"].strip() == "critical")
    return {
        "n": len(rows),
        "correct": correct,
        "accuracy": round(correct / len(rows), 4) if rows else None,
        "over_calls": over,
        "under_calls": under,
        "dangerous_misses": len(dangerous),
        "n_gold_critical": n_critical,
        "critical_recall": round((n_critical - len(dangerous)) / n_critical, 4) if n_critical else None,
        "by_script": {s: {"n": len(v), "correct": sum(v),
                          "accuracy": round(sum(v) / len(v), 4)}
                      for s, v in sorted(by_script.items())},
        "dangerous_miss_detail": dangerous,
        "misses": misses,
    }


def gold_dedup_pairs(rows: list[dict]) -> list[tuple]:
    """Every same-category pair among rows that carry a dup_group, labelled
    duplicate when the groups match. Rows without a group are excluded: a
    blank means "not assessed for duplicates", not "duplicate of nothing".
    """
    grouped = [r for r in rows if r["dup_group"].strip()]
    pairs = []
    for a, b in combinations(grouped, 2):
        if a["category"] != b["category"]:
            continue
        pairs.append((a, b, a["dup_group"].strip() == b["dup_group"].strip()))
    return pairs


def dedup_eval(scored: list[tuple], threshold: float) -> dict:
    tp = sum(1 for dup, sim in scored if dup and sim >= threshold)
    fn = sum(1 for dup, sim in scored if dup and sim < threshold)
    fp = sum(1 for dup, sim in scored if not dup and sim >= threshold)
    tn = sum(1 for dup, sim in scored if not dup and sim < threshold)
    predicted = tp + fp
    actual = tp + fn
    # precision is None, not 0.0, when nothing was predicted duplicate: "no
    # wrong answers because no answers" is not the same as "all answers wrong".
    precision = round(tp / predicted, 4) if predicted else None
    recall = round(tp / actual, 4) if actual else None
    f1 = None
    if precision and recall:
        f1 = round(2 * precision * recall / (precision + recall), 4)
    return {
        "threshold": threshold, "true_positives": tp, "false_negatives": fn,
        "false_positives": fp, "true_negatives": tn,
        "precision": precision, "recall": recall, "f1": f1,
    }


def threshold_sweep(scored: list[tuple], candidates: list[float] = None) -> list[dict]:
    return [dedup_eval(scored, t) for t in (candidates if candidates is not None else SWEEP)]


def best_threshold(sweep: list[dict]) -> dict | None:
    """Highest F1, and on a tie the HIGHER threshold.

    Several thresholds often score an identical F1 on a small gold set, and
    plain max() would then pick whichever came first in the list. The tie-break
    is a real decision, not a formality: a wrong merge buries one citizen's
    complaint inside another's issue, while a missed merge only leaves a
    duplicate, so the conservative end of a tie is the right end.
    """
    usable = [s for s in sweep if s["f1"] is not None]
    return max(usable, key=lambda s: (s["f1"], s["threshold"])) if usable else None


def _score_pairs(pairs: list[tuple]) -> list[tuple]:
    if not pairs:
        return []
    model = get_embedding_model()
    texts = sorted({r["text"] for pair in pairs for r in pair[:2]})
    vectors = dict(zip(texts, model.encode(texts, show_progress_bar=False)))
    return [(dup, _cosine_similarity(vectors[a["text"]], vectors[b["text"]]))
            for a, b, dup in pairs]


def _evaluate(rows: list[dict], label: str) -> dict:
    pairs = gold_dedup_pairs(rows)
    scored = _score_pairs(pairs)
    sweep = threshold_sweep(scored)
    return {
        "split": label,
        "n_complaints": len(rows),
        "severity": severity_eval(rows),
        "dedup": {
            "n_pairs": len(scored),
            "n_duplicate_pairs": sum(1 for dup, _ in scored if dup),
            "at_current_threshold": dedup_eval(scored, COSINE_THRESHOLD),
            "best_by_f1": best_threshold(sweep),
            "sweep": sweep,
        },
    }


def _majority_baseline(rows: list[dict]) -> dict:
    """Always answering the most common band. Severity has to beat this to be
    adding any information at all - and before this commit it did not."""
    counts: dict[str, int] = {}
    for r in rows:
        band = r["severity"].strip()
        counts[band] = counts.get(band, 0) + 1
    if not counts:
        return {"band": None, "accuracy": None}
    band, n = max(counts.items(), key=lambda kv: kv[1])
    return {"band": band, "accuracy": round(n / len(rows), 4)}


def main() -> None:
    rows = load_gold()
    test_rows = [r for r in rows if r["split"] == "test"]

    untouched = [r for r in rows if r["gold_id"] not in TUNED_ON_GOLD_IDS]

    report = {
        "gold_csv": GOLD_CSV,
        "current_cosine_threshold": COSINE_THRESHOLD,
        "clean_test_split": _evaluate(test_rows, "test"),
        "all_rows_leaky": _evaluate(rows, "all (includes 42 seed rows the encoder was tuned around)"),
        # The only defensible held-out severity number: rows never read while
        # choosing keywords. Dedup is omitted here - its holdout is seed/test.
        "severity_not_tuned_on": {
            "note": "rows never inspected while choosing severity keywords; "
                    "the honest held-out severity score",
            "n_excluded": len(rows) - len(untouched),
            **severity_eval(untouched),
            "majority_class_baseline": _majority_baseline(untouched),
        },
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    for key in ("clean_test_split", "all_rows_leaky"):
        section = report[key]
        sev, ded = section["severity"], section["dedup"]
        print(f"\n=== {key}  ({section['n_complaints']} complaints)")
        print(f"  severity accuracy : {sev['accuracy']}  ({sev['correct']}/{sev['n']})")
        print(f"      over-called {sev['over_calls']}  under-called {sev['under_calls']}  "
              f"DANGEROUS misses {sev['dangerous_misses']}/{sev['n_gold_critical']} gold-critical "
              f"(critical recall {sev['critical_recall']})")
        for script, s in sev["by_script"].items():
            print(f"      {script:11}     {s['accuracy']}  ({s['correct']}/{s['n']})")
        print(f"  dedup pairs       : {ded['n_pairs']} ({ded['n_duplicate_pairs']} duplicates)")
        cur = ded["at_current_threshold"]
        print(f"      at {cur['threshold']:<5}        precision {cur['precision']}  "
              f"recall {cur['recall']}  f1 {cur['f1']}")
        best = ded["best_by_f1"]
        if best:
            print(f"      best f1 at {best['threshold']:<5} precision {best['precision']}  "
                  f"recall {best['recall']}  f1 {best['f1']}")
    held = report["severity_not_tuned_on"]
    base = held["majority_class_baseline"]
    print(f"\n=== severity, HELD OUT ({held['n']} rows never read while tuning; "
          f"{held['n_excluded']} excluded)")
    print(f"  accuracy          : {held['accuracy']}")
    print(f"  always-'{base['band']}'   : {base['accuracy']}   <- must beat this")
    print(f"  critical recall   : {held['critical_recall']}  "
          f"({held['dangerous_misses']} dangerous misses of {held['n_gold_critical']})")
    for script, st in held["by_script"].items():
        print(f"      {script:11}   {st['accuracy']}  ({st['correct']}/{st['n']})")
    print(f"\nwrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
