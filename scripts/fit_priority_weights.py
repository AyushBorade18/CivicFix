"""Fit the priority weights (app/core/priority.py) to human pairwise reviews.

Inputs, all in data/labelling/:
  priority_issues.csv              the 400 labelled synthetic issues
  priority_pair_reviews_*.csv      one file per reviewer

Each issue is turned into the four terms the app itself computes, then a
Bradley-Terry model (logistic regression on term differences, no intercept,
weights >= 0) is fitted to the A/B decisions. SAME and CANNOT_DETERMINE are
dropped. Output is printed only - copying weights into priority.py is a
human decision.

    python -m scripts.fit_priority_weights
"""
import csv
import glob
import random

import numpy as np
from scipy.optimize import minimize

from app.core import priority as P

DIR = "data/labelling"
TERMS = ("exposure", "severity", "recurrence", "time_open")

# Pool labels -> the app's term values. The app has no "high" band, so it
# lands on critical: the app would score it 1.0 as well.
SEVERITY = {"low": 0.0, "moderate": 0.5, "high": 1.0, "critical": 1.0}
RECURRENCE = {"first_report": 0.0, "occasional": 0.5, "recurring": 1.0}


def terms(row, age_cap_days=P.TIME_OPEN_NORM_DAYS):
    site = row["sensitive_site"]
    exposure = P._site_weight(site, row["category"]) if site != "none" else 0.0
    return [
        exposure,
        SEVERITY[row["severity_level"]],
        RECURRENCE[row["recurrence_pattern"]],
        min(int(row["issue_age_days"]) / age_cap_days, 1.0),
    ]


def load_pairs():
    """(winner_id, loser_id, pair_id, reviewer) for every A/B decision."""
    pairs = []
    for path in sorted(glob.glob(f"{DIR}/priority_pair_reviews_*.csv")):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if r["decision"] not in ("A", "B"):
                continue
            ids = {r["shown_left_issue_id"], r["shown_right_issue_id"]}
            winner = r["chosen_issue_id"]
            (loser,) = ids - {winner}
            pairs.append((winner, loser, r["pair_id"], r["reviewer_id"]))
    return pairs


def diff_matrix(pairs, issues, age_cap_days):
    return np.array([
        np.subtract(terms(issues[w], age_cap_days), terms(issues[l], age_cap_days))
        for w, l, _, _ in pairs
    ])


def fit(X):
    """Non-negative Bradley-Terry weights, rescaled to sum to 1."""
    def nll(w):
        z = X @ w
        return np.logaddexp(0, -z).sum() + 0.01 * w @ w  # tiny ridge keeps it bounded

    w = minimize(nll, np.ones(X.shape[1]), bounds=[(0, None)] * X.shape[1]).x
    return w / w.sum() if w.sum() > 0 else w


def agreement(X, w):
    """Share of pairs where the formula ranks the human's pick higher; ties count half."""
    z = X @ w
    return ((z > 1e-9).sum() + 0.5 * (np.abs(z) <= 1e-9).sum()) / len(z)


def cross_validate(X, folds=5, repeats=20, seed=0):
    rng = random.Random(seed)
    scores = []
    for _ in range(repeats):
        idx = list(range(len(X)))
        rng.shuffle(idx)
        for k in range(folds):
            test = idx[k::folds]
            train = [i for i in idx if i not in set(test)]
            scores.append(agreement(X[test], fit(X[train])))
    return float(np.mean(scores))


def main():
    issues = {r["issue_id"]: r for r in csv.DictReader(open(f"{DIR}/priority_issues.csv", encoding="utf-8"))}
    pairs = load_pairs()
    reviewers = sorted({p[3] for p in pairs})
    print(f"{len(pairs)} A/B decisions from reviewer(s) {', '.join(reviewers)}")

    current = np.array([P.W_EXPOSURE, P.W_SEVERITY, P.W_RECURRENCE, P.W_TIME_OPEN])
    print(f"current weights {dict(zip(TERMS, current))}")
    print("\ntime-open cap   fitted (exp, sev, rec, time)   fitted in-sample   fitted 5-fold CV   current weights")
    for cap in (90, 180, 365, 750):
        Xc = diff_matrix(pairs, issues, cap)
        w = fit(Xc)
        print(f"  {cap:>4} days    {np.round(w, 2)}      {agreement(Xc, w):.1%}              "
              f"{cross_validate(Xc):.1%}              {agreement(Xc, current):.1%}")


if __name__ == "__main__":
    main()
