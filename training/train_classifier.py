"""Train the category classifier: sentence embeddings -> LogisticRegression.

Data (all labelled by source, never mixed silently):
  - icmyc_bengaluru       real English complaints, Bengaluru (training/icmyc_mapped.csv)
  - synthetic_complaints  synthetic Pune, 7 language styles (training/synthetic/complaints.csv)
  - synthetic_groups      synthetic Pune paraphrase groups (training/synthetic/paraphrase_groups.csv)
NYC 311 is left out: its terse US descriptors made the old model call Pune
complaints "other" (see ARCHIVED_MODEL_PATH note in app/nlp/classify.py).

Weighting: real and synthetic data get equal total weight, and categories
are balanced within each, so 14k English rows can't drown the multilingual ones.

Evaluation: held-out 15% of iCMyC and synthetic complaints (stratified by
category) plus the paraphrase groups the encoder never saw. Reported overall,
per source, per language, per category, against the keyword baseline, and
coverage/accuracy per confidence threshold. These are synthetic/Bengaluru
numbers; real-world accuracy comes from the human test set (--eval-human).

Output: models/classifier_v1.pkl (+ the encoder name it was trained with) and
models/classifier_metrics_v1.json. Not live until copied to classify.MODEL_PATH.

Run:
  python -m training.train_classifier [--encoder models/civicfix-encoder-v1]
  python -m training.train_classifier --eval-human data/labelling/lo2_gold_complaints.csv
"""
import argparse
import csv
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from app.categories import CIVIC_CATEGORIES
from training.finetune_encoder import split_groups

ROOT = Path(__file__).resolve().parent.parent
ICMYC_CSV = ROOT / "training/icmyc_mapped.csv"
COMPLAINTS_CSV = ROOT / "training/synthetic/complaints.csv"
GROUPS_CSV = ROOT / "training/synthetic/paraphrase_groups.csv"
DEFAULT_ENCODER = ROOT / "models/civicfix-encoder-v1"
MODEL_OUT = ROOT / "models/classifier_v1.pkl"
METRICS_OUT = ROOT / "models/classifier_metrics_v1.json"

SEED = 42
TEST_SHARE = 0.15
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
REAL_SOURCES = {"icmyc_bengaluru"}


def _read(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_all_sources() -> list[dict]:
    rows = [{"text": r["text"], "category": r["category"], "language": "english",
             "source": "icmyc_bengaluru", "group_id": ""} for r in _read(ICMYC_CSV)]
    rows += [{"text": r["text"], "category": r["category"], "language": r["language"],
              "source": "synthetic_complaints", "group_id": ""} for r in _read(COMPLAINTS_CSV)]
    rows += [{"text": r["text"], "category": r["category"], "language": r["language"],
              "source": "synthetic_groups", "group_id": r["group_id"]} for r in _read(GROUPS_CSV)]
    return rows


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Groups: the encoder's held-out groups go to test (whole groups only).
    Other sources: stratified TEST_SHARE per category, seeded."""
    groups = [r for r in rows if r["source"] == "synthetic_groups"]
    _, test_groups = split_groups(groups)
    test_ids = {r["group_id"] for r in test_groups}
    train, test = [], []
    for r in groups:
        (test if r["group_id"] in test_ids else train).append(r)
    rng = random.Random(SEED)
    buckets = defaultdict(list)
    for r in rows:
        if r["source"] != "synthetic_groups":
            buckets[(r["source"], r["category"])].append(r)
    for key in sorted(buckets):
        items = buckets[key][:]
        rng.shuffle(items)
        n_test = max(1, round(len(items) * TEST_SHARE))
        test += items[:n_test]
        train += items[n_test:]
    return train, test


def sample_weights(rows: list[dict]) -> list[float]:
    """Real vs synthetic halves carry equal total weight; within each half,
    every category carries equal weight."""
    half = len(rows) / 2
    side = lambda r: "real" if r["source"] in REAL_SOURCES else "synth"  # noqa: E731
    counts = Counter((side(r), r["category"]) for r in rows)
    cats_per_half = Counter(s for s, _ in counts)
    return [half / cats_per_half[side(r)] / counts[(side(r), r["category"])] for r in rows]


def threshold_table(confidences: np.ndarray, correct: np.ndarray, thresholds=THRESHOLDS) -> list[dict]:
    table = []
    for t in thresholds:
        kept = confidences >= t
        table.append({"threshold": t, "coverage": round(float(kept.mean()), 3),
                      "accuracy": round(float(correct[kept].mean()), 3) if kept.any() else None})
    return table


def _macro_f1(y_true, y_pred) -> float:
    from sklearn.metrics import f1_score
    return round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 3)


def report(rows: list[dict], predicted: list[str], confidences: np.ndarray) -> dict:
    from sklearn.metrics import confusion_matrix, f1_score

    from app.nlp.classify import classify_keywords

    truth = [r["category"] for r in rows]
    correct = np.array([p == t for p, t in zip(predicted, truth)])

    def by(key):
        return {v: _macro_f1([t for t, r in zip(truth, rows) if r[key] == v],
                             [p for p, r in zip(predicted, rows) if r[key] == v])
                for v in sorted({r[key] for r in rows})}

    labels = list(CIVIC_CATEGORIES)
    per_cat = f1_score(truth, predicted, labels=labels, average=None, zero_division=0)
    return {
        "n": len(rows),
        "macro_f1": _macro_f1(truth, predicted),
        "keyword_baseline_macro_f1": _macro_f1(truth, [classify_keywords(r["text"])[0] for r in rows]),
        "macro_f1_by_source": by("source"),
        "macro_f1_by_language": by("language"),
        "f1_by_category": {c: round(float(x), 3) for c, x in zip(labels, per_cat)},
        "confusion_matrix": {"labels": labels,
                             "rows_true_cols_pred": confusion_matrix(truth, predicted, labels=labels).tolist()},
        "confidence_thresholds": threshold_table(confidences, correct),
    }


def _fit(x, rows):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    enc = LabelEncoder().fit(list(CIVIC_CATEGORIES))
    clf = LogisticRegression(max_iter=3000)
    clf.fit(x, enc.transform([r["category"] for r in rows]), sample_weight=sample_weights(rows))
    return clf, enc


def _predict(clf, enc, x):
    probs = clf.predict_proba(x)
    return list(enc.inverse_transform(probs.argmax(axis=1))), probs.max(axis=1)


def _encoder_name(path_or_name: str) -> str:
    p = Path(path_or_name)
    return str(p.resolve().relative_to(ROOT)) if p.exists() else path_or_name


def train_and_save(encoder: str) -> dict:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(encoder)

    def embed(rs):
        return model.encode([r["text"] for r in rs], batch_size=64, normalize_embeddings=True,
                            show_progress_bar=False)

    rows = load_all_sources()
    train, test = split_rows(rows)
    print(f"train {len(train)}, test {len(test)}; embedding with {encoder}", flush=True)
    x_train, x_test = embed(train), embed(test)
    clf, enc = _fit(x_train, train)
    held_out = report(test, *_predict(clf, enc, x_test))
    print(json.dumps({k: held_out[k] for k in ("macro_f1", "keyword_baseline_macro_f1",
                                                "macro_f1_by_source", "macro_f1_by_language")},
                     ensure_ascii=False))

    clf, enc = _fit(np.vstack([x_train, x_test]), train + test)  # ship: fit on everything
    trained_on = dict(Counter(r["source"] for r in rows))
    with open(MODEL_OUT, "wb") as f:
        pickle.dump({"model": clf, "label_encoder": enc, "encoder": _encoder_name(encoder),
                     "trained_on": trained_on}, f)
    metrics = {"encoder": _encoder_name(encoder), "seed": SEED, "test_share": TEST_SHARE,
               "trained_on": trained_on, "held_out": held_out,
               "note": "Held-out rows are Bengaluru (real, English) or synthetic. Report real-world "
                       "accuracy from the human test set only."}
    METRICS_OUT.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    return metrics


def evaluate_human(csv_path: str, model_path: Path = MODEL_OUT) -> dict:
    """Scores the saved classifier on the human-written test set
    (columns: text, final_category, language)."""
    from sentence_transformers import SentenceTransformer
    with open(model_path, "rb") as f:
        saved = pickle.load(f)
    rows = [{"text": r["text"], "category": r["final_category"], "language": r["language"],
             "source": "human_test_set", "group_id": ""}
            for r in _read(Path(csv_path)) if r.get("final_category") and r.get("text")]
    encoder = saved["encoder"]
    encoder = str(ROOT / encoder) if (ROOT / encoder).exists() else encoder
    x = SentenceTransformer(encoder).encode([r["text"] for r in rows], normalize_embeddings=True,
                                            show_progress_bar=False)
    return report(rows, *_predict(saved["model"], saved["label_encoder"], x))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoder", default=str(DEFAULT_ENCODER) if DEFAULT_ENCODER.exists()
                        else "paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--eval-human", metavar="CSV")
    args = parser.parse_args()
    if args.eval_human:
        print(json.dumps(evaluate_human(args.eval_human), indent=2, ensure_ascii=False))
    else:
        train_and_save(args.encoder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
