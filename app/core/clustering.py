import json
import math

import numpy as np
from sklearn.cluster import DBSCAN

from app.db import get_connection

# PROVISIONAL for the fine-tuned encoder (models/civicfix-encoder-v1). On the
# 48 held-out synthetic paraphrase groups, same-category pairs: at 0.80, 51% of
# true duplicates pass on text alone at 96% precision; same-place different
# problems pass 3/27. Distance and time gates below remove most other false
# merges. Conservative on purpose (a wrong merge is worse than a missed one).
# Re-tune on the human-labelled pairs in data/labelling/lo3_dedup_pairs.csv.
COSINE_THRESHOLD = 0.80
DISTANCE_THRESHOLD_M = 100
TIME_WINDOW_DAYS = 7

# Distance assigned to any pair that fails category/spatial/time gating, so
# they can never land in the same DBSCAN cluster (must exceed _EPS).
_DISQUALIFIED = 10.0
_EPS = 1.0 - COSINE_THRESHOLD


def _parse_embedding(raw) -> np.ndarray:
    return np.array(json.loads(raw)) if isinstance(raw, str) else np.array(raw)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def spatial_ok(r1: dict, r2: dict) -> bool:
    """Real ARCHITECTURE.md 5.5 rule is haversine <= 100m on the stored geom.
    That's only trustworthy between two PRECISE (geom_confidence=1.0)
    points. Most of this dataset's reports resolved to a ward centroid
    (confidence 0.4) - every ward-level report in the same ward shares the
    literal same point, so a naive haversine check would silently report
    "0m apart" between reports that could be km apart in reality. Deviation
    (explicitly requested): when either side is ward-level, require the
    same ward instead of trusting centroid distance as real proximity.
    """
    if r1["geom_confidence"] == 1.0 and r2["geom_confidence"] == 1.0:
        return _haversine_m(r1["lat"], r1["lon"], r2["lat"], r2["lon"]) <= DISTANCE_THRESHOLD_M
    return r1["ward_id"] is not None and r1["ward_id"] == r2["ward_id"]


def _time_ok(r1: dict, r2: dict) -> bool:
    delta = abs((r1["reported_at"] - r2["reported_at"]).days)
    return delta <= TIME_WINDOW_DAYS


def cluster_reports(reports: list[dict]) -> dict[int, int]:
    """Groups reports into issues per ARCHITECTURE.md 5.5: same category,
    cosine similarity >= 0.82, haversine <= 100m (or ward match - see
    spatial_ok), reported within a 7-day window - via DBSCAN over a
    precomputed combined-distance matrix so all three conditions must hold
    simultaneously for two reports to land in the same cluster.

    Returns {report_id: local_cluster_label}. Labels are provisional
    (unique within this call only) - persisting them as real `issues` rows
    is run_clustering()'s job, not this pure function's.
    """
    result: dict[int, int] = {}
    label_offset = 0

    by_category: dict[str, list[dict]] = {}
    for r in reports:
        by_category.setdefault(r["category"], []).append(r)

    for category, group in by_category.items():
        k = len(group)
        if k == 0:
            continue
        if k == 1:
            result[group[0]["id"]] = label_offset
            label_offset += 1
            continue

        dist = np.full((k, k), _DISQUALIFIED)
        np.fill_diagonal(dist, 0.0)
        for i in range(k):
            for j in range(i + 1, k):
                r1, r2 = group[i], group[j]
                if spatial_ok(r1, r2) and _time_ok(r1, r2):
                    sim = _cosine_similarity(r1["embedding"], r2["embedding"])
                    if sim >= COSINE_THRESHOLD:
                        # Identical/near-identical embeddings (repeated
                        # templates in the synthetic data) can push floating
                        # point similarity a hair above 1.0, making 1-sim
                        # negative - sklearn's precomputed-distance check
                        # rejects negative values.
                        d = max(0.0, 1.0 - sim)
                        dist[i, j] = d
                        dist[j, i] = d

        labels = DBSCAN(eps=_EPS, min_samples=1, metric="precomputed").fit_predict(dist)
        for local_label, report in zip(labels, group):
            result[report["id"]] = label_offset + int(local_label)
        label_offset += int(labels.max()) + 1

    return result


def fetch_reports_for_clustering(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, category, embedding, reported_at, geom_confidence,
                   ward_id, ST_Y(geom), ST_X(geom)
            FROM reports
            WHERE category IS NOT NULL
            """
        )
        rows = cur.fetchall()

    reports = []
    for (report_id, category, embedding, reported_at, geom_confidence,
         ward_id, lat, lon) in rows:
        reports.append({
            "id": report_id,
            "category": category,
            "embedding": _parse_embedding(embedding),
            "reported_at": reported_at,
            "geom_confidence": geom_confidence,
            "ward_id": ward_id,
            "lat": lat,
            "lon": lon,
        })
    return reports


def run_clustering(conn=None) -> int:
    """Orchestration: fetches all reports, clusters them, and (re)writes the
    `issues` table plus reports.issue_id from scratch. Not part of the 5.5
    contract itself (that's cluster_reports above) - this is the glue the
    demo's "run it" button and this session's reporting both need.
    """
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        reports = fetch_reports_for_clustering(conn)
        by_id = {r["id"]: r for r in reports}
        labels = cluster_reports(reports)

        members_by_label: dict[int, list[int]] = {}
        for report_id, label in labels.items():
            members_by_label.setdefault(label, []).append(report_id)

        with conn.cursor() as cur:
            # NOT "TRUNCATE issues CASCADE": issues is referenced by
            # reports.issue_id, matches.issue_id and signals.issue_id, and
            # CASCADE truncates every referencing table too - this would
            # silently wipe all 400 real reports on every clustering run.
            # Null the FK first, then plain DELETE (blocked by the FK if
            # anything still points at a row, which is exactly what we want).
            cur.execute("UPDATE reports SET issue_id = NULL")
            cur.execute("DELETE FROM signals")
            cur.execute("DELETE FROM matches")
            cur.execute("DELETE FROM issues")

            for member_ids in members_by_label.values():
                members = [by_id[rid] for rid in member_ids]
                category = members[0]["category"]
                lats = [m["lat"] for m in members if m["lat"] is not None]
                lons = [m["lon"] for m in members if m["lon"] is not None]
                ward_ids = [m["ward_id"] for m in members if m["ward_id"] is not None]
                ward_id = max(set(ward_ids), key=ward_ids.count) if ward_ids else None
                reported_ats = [m["reported_at"] for m in members]
                embedding = np.mean([m["embedding"] for m in members], axis=0)
                embedding_literal = "[" + ",".join(str(float(v)) for v in embedding) + "]"

                geom_expr = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)" if lats else "NULL"
                geom_params = (sum(lons) / len(lons), sum(lats) / len(lats)) if lats else ()

                cur.execute(
                    f"""
                    INSERT INTO issues (
                        category, geom, ward_id, first_reported, last_reported,
                        report_count, status, embedding
                    ) VALUES (
                        %s, {geom_expr}, %s, %s, %s, %s, 'open', %s::vector
                    ) RETURNING id
                    """,
                    (
                        category, *geom_params, ward_id,
                        min(reported_ats), max(reported_ats), len(members),
                        embedding_literal,
                    ),
                )
                issue_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE reports SET issue_id = %s WHERE id = ANY(%s)",
                    (issue_id, member_ids),
                )
        conn.commit()
        return len(members_by_label)
    finally:
        if owns_conn:
            conn.close()
