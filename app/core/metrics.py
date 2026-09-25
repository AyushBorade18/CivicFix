"""Real evaluation numbers for GET /api/metrics, per ARCHITECTURE.md section
6: "build this, it is cheap and it convinces." Every number here is computed
from the actual database or a persisted offline evaluation run - nothing is
asserted without a query or a saved result backing it.

Two honest simplifications, stated plainly rather than silently:
- Deduplication (clustering) precision/recall against a fuzzy-string/TF-IDF
  baseline needs hand-labeled "these reports are the same issue" ground
  truth, which doesn't exist. Descriptive cluster-size stats are reported
  instead of a fabricated precision/recall pair.
- Location extraction reports the real resolved/ward-level/unresolved
  breakdown from the reports table. No separate "regex+gazetteer only"
  baseline run is stored to compare against - only the full pipeline's
  actual outcome is reported.
"""
import json
import os

from app.db import get_connection
from app.nlp.classify import MODEL_PATH

# Metrics of the model actually behind classify(), i.e. MODEL_PATH
# (models/classifier_v1.pkl). NOT models/classifier_metrics.json - those
# belong to the retired NYC-311 model that app.nlp.classify deliberately
# keeps at ARCHIVED_MODEL_PATH *because* it is no longer deployed. Serving
# the archived model's 0.929 while v1 was live meant /api/metrics (and the
# admin Verification page) reported a score the running system never produces.
CLASSIFIER_METRICS_PATH = "models/classifier_human_eval_v1.json"
# Training-set size lives in the training run's own file; the human-eval
# record is evaluation-only and does not carry it.
CLASSIFIER_TRAINING_PATH = "models/classifier_metrics_v1.json"


def classification_metrics() -> dict:
    # "trained" and "deployed" are deliberately different facts: a model can
    # be trained and honestly evaluated (real numbers exist) without being
    # the live classify() path - see app.nlp.classify.ARCHIVED_MODEL_PATH.
    deployed = os.path.exists(MODEL_PATH)
    if not os.path.exists(CLASSIFIER_METRICS_PATH):
        return {
            "model_macro_f1": None, "baseline_macro_f1": None,
            "n_train": None, "n_test": None, "trained": False, "deployed": deployed,
        }
    with open(CLASSIFIER_METRICS_PATH) as f:
        data = json.load(f)

    # n_train is not part of the evaluation record; read it from the training
    # run when that file exists rather than inferring or asserting a number.
    n_train = None
    if os.path.exists(CLASSIFIER_TRAINING_PATH):
        with open(CLASSIFIER_TRAINING_PATH) as f:
            trained_on = json.load(f).get("trained_on") or {}
        n_train = sum(trained_on.values()) or None

    return {
        # Held-out evaluation on human-written complaints - the defensible
        # judge-facing number, not the synthetic-heavy held-out split.
        "model_macro_f1": data.get("macro_f1"),
        "baseline_macro_f1": data.get("keyword_baseline_macro_f1"),
        "n_train": n_train,
        "n_test": data.get("n"),
        "trained": True,
        "deployed": deployed,
    }


def clustering_metrics(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE report_count = 1), "
            "count(*) FILTER (WHERE report_count > 1), COALESCE(max(report_count), 0) FROM issues"
        )
        total, singleton, multi, largest = cur.fetchone()
    return {
        "total_issues": total, "singleton_issues": singleton,
        "multi_report_issues": multi, "largest_cluster_size": largest,
    }


def location_metrics(conn) -> dict:
    # geom_confidence is `real` (float4): 1.0 is exactly representable in
    # binary, so `= 1.0` is safe, but 0.4 is not, so `= 0.4` can silently
    # match zero rows even for actual 0.4 values - found by a failing test,
    # not by inspection. "< 1.0" sidesteps the float-equality trap entirely.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE geom_confidence = 1.0), "
            "count(*) FILTER (WHERE geom_confidence IS NOT NULL AND geom_confidence < 1.0), "
            "count(*) FILTER (WHERE geom IS NULL) FROM reports"
        )
        total, precise, ward, unresolved = cur.fetchone()
    resolved = precise + ward
    return {
        "total_reports": total, "precise_resolved": precise, "ward_level_resolved": ward,
        "unresolved": unresolved, "resolution_rate": round(resolved / total, 4) if total else 0.0,
    }


def matcher_metrics(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM issues WHERE category != 'other'")
        eligible = cur.fetchone()[0]
        cur.execute("SELECT count(DISTINCT issue_id) FROM matches")
        matched = cur.fetchone()[0]

        # "Hand-labeled" cases: an issue whose centroid exactly equals a
        # real, resolved, non-'other' MPLADS work's point in the same
        # category. This is a genuine known ground truth - the synthetic
        # generator deliberately seeded reports at these exact anchor
        # points - not a label invented after seeing the matcher's output.
        cur.execute(
            """
            SELECT i.id, w.id FROM issues i
            JOIN works w ON w.geom = i.geom AND w.category = i.category
            WHERE w.geom IS NOT NULL AND w.category != 'other'
            """
        )
        labeled = cur.fetchall()

        correct = 0
        for issue_id, expected_work_id in labeled:
            cur.execute(
                "SELECT work_id FROM matches WHERE issue_id = %s ORDER BY combined_score DESC LIMIT 1",
                (issue_id,),
            )
            row = cur.fetchone()
            if row and row[0] == expected_work_id:
                correct += 1

    return {
        "total_issues_eligible": eligible,
        "matched_issues": matched,
        "match_rate": round(matched / eligible, 4) if eligible else 0.0,
        "labeled_cases": len(labeled),
        "labeled_correct": correct,
        "labeled_accuracy": round(correct / len(labeled), 4) if labeled else None,
    }


def compute_metrics(conn=None) -> dict:
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        return {
            "classification": classification_metrics(),
            "clustering": clustering_metrics(conn),
            "location": location_metrics(conn),
            "matcher": matcher_metrics(conn),
        }
    finally:
        if owns_conn:
            conn.close()
