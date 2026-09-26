"""LO3: generate report <-> report DEDUPLICATION candidate pairs for review.

    python -m scripts.lo3.dedup_pairs

Candidates only - nothing here is a label. The point of the labels this file
collects is to re-tune app/core/clustering.py's COSINE_THRESHOLD (its comment
says so): right now that threshold rests on synthetic paraphrase groups only.

So the gates are imported from clustering rather than re-implemented - a
candidate set built on a drifted copy of spatial_ok would be measuring the
wrong system. What this script does NOT use is the `issues` table or
reports.issue_id: those are the clusterer's own output, and grading a
clusterer against its own decisions is circular.

Buckets (pair_type), chosen so the labels can settle a specific question:
  likely_duplicate             gates pass, sim >= threshold -> would merge today
  boundary_below_threshold     gates pass, sim in [0.65, threshold) -> THE band
                               that decides where the threshold should sit
  gated_low_similarity         gates pass, sim in [0.45, 0.65) -> expected to be
                               non-duplicates, but that is the human's call, not
                               this script's (early runs found real-looking
                               duplicates down here, which is worth knowing)
  outside_time_window          same ward, sim high, > TIME_WINDOW_DAYS apart ->
                               is the 7-day gate dropping real recurrences?
  different_ward_high_similar.  sim high, in window, different ward -> is the
                               ward gate too strict at ward boundaries?
  cross_category_same_place_time  different category, same ward, in window,
                               sim >= 0.50 -> a classifier split that stops two
                               reports of one problem from EVER being compared

Output: data/labelling/lo3_dedup_pairs.csv, deterministic, <= MAX_EXAMPLES
rows, no report reused across rows. label_a/label_b/final_label/notes are
left empty: no plan doc in the repo defines whether label_a/label_b mean the
two sides' categories or two reviewers' independent verdicts, so this script
fills neither and lets the reviewers use them as intended.
"""
import csv
from itertools import combinations
from pathlib import Path

from app.core.clustering import (
    COSINE_THRESHOLD,
    TIME_WINDOW_DAYS,
    _cosine_similarity,
    _parse_embedding,
    spatial_ok,
)
from app.db import get_connection

OUTPUT_CSV = Path("data/labelling/lo3_dedup_pairs.csv")
OUTPUT_COLUMNS = [
    "pair_id", "text_a", "locality_a", "text_b", "locality_b", "days_apart",
    "label_a", "label_b", "final_label", "pair_type", "notes",
]

BOUNDARY_LOW = 0.65          # bottom of the "could go either way" band
SAME_PLACE_LOW = 0.45        # below this, a same-place pair is obviously unrelated
CROSS_CATEGORY_LOW = 0.50    # cross-category pairs worth a second look

# Scaled to what a full scan actually finds - see the "bucket sizes" line this
# script prints. Never set above what genuinely exists.
#
# ORDER MATTERS: select_examples fills buckets in this order and never reuses a
# report, so whatever runs first eats the shared supply. The scarce buckets that
# actually settle a question go first; likely_duplicate and the two gate checks
# have hundreds of candidates each and still fill their quota from the leftovers.
BUCKET_QUOTA = {
    "boundary_below_threshold": 25,
    "cross_category_same_place_time": 8,
    "gated_low_similarity": 15,
    "likely_duplicate": 25,
    "outside_time_window": 12,
    "different_ward_high_similarity": 10,
}
MAX_EXAMPLES = 95


def pair_type(a: dict, b: dict, sim: float, days_apart: int) -> str | None:
    """Why this pair is worth a human's time - not what its label is."""
    same_ward = a["ward_id"] is not None and a["ward_id"] == b["ward_id"]
    located_together = spatial_ok(a, b)
    in_window = days_apart <= TIME_WINDOW_DAYS

    if a["category"] != b["category"]:
        if same_ward and in_window and sim >= CROSS_CATEGORY_LOW:
            return "cross_category_same_place_time"
        return None

    if located_together and in_window:
        if sim >= COSINE_THRESHOLD:
            return "likely_duplicate"
        if sim >= BOUNDARY_LOW:
            return "boundary_below_threshold"
        if sim >= SAME_PLACE_LOW:
            return "gated_low_similarity"
        return None

    if sim < COSINE_THRESHOLD:
        return None
    if located_together and not in_window:
        return "outside_time_window"
    if in_window and not same_ward:
        return "different_ward_high_similarity"
    return None


def load_reports(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.raw_text, r.category, r.ward_id, w.name, r.reported_at,
                   r.geom_confidence, r.embedding, ST_Y(r.geom), ST_X(r.geom)
            FROM reports r
            LEFT JOIN wards w ON w.id = r.ward_id
            WHERE r.category IS NOT NULL AND r.embedding IS NOT NULL
            ORDER BY r.id
            """
        )
        rows = cur.fetchall()

    reports = []
    for (rid, text, category, ward_id, ward_name, reported_at, geom_conf,
         embedding, lat, lon) in rows:
        reports.append({
            "id": rid,
            "text": (text or "").strip(),
            "category": category,
            "ward_id": ward_id,
            "reported_at": reported_at,
            "geom_confidence": geom_conf,
            "embedding": _parse_embedding(embedding),
            "lat": lat,
            "lon": lon,
            "locality": f"PMC ward {ward_id} {ward_name}".strip() if ward_id else "unplaced",
        })
    return reports


def build_candidates(reports: list[dict]) -> list[tuple]:
    candidates = []
    for a, b in combinations(reports, 2):
        days_apart = abs((a["reported_at"] - b["reported_at"]).days)
        sim = _cosine_similarity(a["embedding"], b["embedding"])
        bucket = pair_type(a, b, sim, days_apart)
        if bucket:
            candidates.append((bucket, a, b, sim, days_apart))
    return candidates


def select_examples(candidates: list[tuple], quota: dict[str, int],
                    max_examples: int) -> list[tuple]:
    """Deterministic pick. A report appears in at most one pair: repetitive
    review material is worse than a smaller set (same rule as LO4's).
    """
    used_reports: set[int] = set()
    used_texts: set[str] = set()
    picked: list[tuple] = []
    for bucket in quota:
        # Verbatim-identical sides are a synthetic-template artefact and teach a
        # reviewer nothing, so they sort last - but they are still offered if a
        # bucket has nothing else (the gate-check buckets often don't).
        in_bucket = sorted(
            (c for c in candidates if c[0] == bucket),
            key=lambda c: (c[1]["text"].lower() == c[2]["text"].lower(),
                           -c[3], c[1]["id"], c[2]["id"]),
        )
        taken = 0
        for candidate in in_bucket:
            if taken >= quota[bucket] or len(picked) >= max_examples:
                break
            _, a, b, _, _ = candidate
            texts = {a["text"].lower(), b["text"].lower()}
            if {a["id"], b["id"]} & used_reports or texts & used_texts:
                continue
            used_reports |= {a["id"], b["id"]}
            used_texts |= texts
            taken += 1
            picked.append(candidate)
    return picked


def main() -> None:
    with get_connection() as conn:
        conn.read_only = True
        reports = load_reports(conn)

    candidates = build_candidates(reports)
    sizes: dict[str, int] = {}
    for bucket, *_ in candidates:
        sizes[bucket] = sizes.get(bucket, 0) + 1

    total_pairs = len(reports) * (len(reports) - 1) // 2
    print(f"reports: {len(reports)}  pairs scanned: {total_pairs}  "
          f"candidates: {len(candidates)}")
    print(f"gates in use: cosine >= {COSINE_THRESHOLD}, "
          f"boundary band [{BOUNDARY_LOW}, {COSINE_THRESHOLD}), "
          f"time window {TIME_WINDOW_DAYS}d")
    print("bucket sizes:", {b: sizes.get(b, 0) for b in BUCKET_QUOTA})

    examples = select_examples(candidates, BUCKET_QUOTA, MAX_EXAMPLES)
    print("picked per bucket:",
          {b: sum(1 for e in examples if e[0] == b) for b in BUCKET_QUOTA})

    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for n, (bucket, a, b, sim, days_apart) in enumerate(examples, start=1):
            writer.writerow({
                "pair_id": f"LO3-{n:03d}",
                "text_a": a["text"],
                "locality_a": a["locality"],
                "text_b": b["text"],
                "locality_b": b["locality"],
                "days_apart": days_apart,
                "label_a": "",
                "label_b": "",
                "final_label": "",      # the human's duplicate / not-duplicate call
                "pair_type": bucket,
                "notes": "",
            })
    print(f"wrote {len(examples)} candidate pairs to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
