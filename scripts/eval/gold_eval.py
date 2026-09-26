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
from app.nlp.severity import severity

GOLD_CSV = "data/labelling/lo2_gold_complaints.csv"
OUTPUT_JSON = Path("data/eval/gold_eval.json")
SWEEP = [round(0.40 + 0.025 * i, 3) for i in range(25)]  # 0.400 .. 0.975


def load_gold(path: str = GOLD_CSV) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def script_of(text: str) -> str:
    return "devanagari" if any("ऀ" <= c <= "ॿ" for c in text or "") else "latin"


def severity_eval(rows: list[dict]) -> dict:
    correct, misses = 0, []
    by_script: dict[str, list[int]] = {}
    for row in rows:
        got = severity(row["text"], row["category"])
        expected = row["severity"].strip()
        hit = got == expected
        correct += hit
        if not hit:
            misses.append({"gold_id": row["gold_id"], "expected": expected, "got": got})
        by_script.setdefault(script_of(row["text"]), []).append(int(hit))
    return {
        "n": len(rows),
        "correct": correct,
        "accuracy": round(correct / len(rows), 4) if rows else None,
        "by_script": {s: {"n": len(v), "correct": sum(v),
                          "accuracy": round(sum(v) / len(v), 4)}
                      for s, v in sorted(by_script.items())},
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


def main() -> None:
    rows = load_gold()
    test_rows = [r for r in rows if r["split"] == "test"]

    report = {
        "gold_csv": GOLD_CSV,
        "current_cosine_threshold": COSINE_THRESHOLD,
        "clean_test_split": _evaluate(test_rows, "test"),
        "all_rows_leaky": _evaluate(rows, "all (includes 42 seed rows the encoder was tuned around)"),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    for key in ("clean_test_split", "all_rows_leaky"):
        section = report[key]
        sev, ded = section["severity"], section["dedup"]
        print(f"\n=== {key}  ({section['n_complaints']} complaints)")
        print(f"  severity accuracy : {sev['accuracy']}  ({sev['correct']}/{sev['n']})")
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
    print(f"\nwrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
