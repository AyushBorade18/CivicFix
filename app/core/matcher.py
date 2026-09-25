import json
import math

import numpy as np

from app.db import get_connection

SEMANTIC_THRESHOLD = 0.5
MATCH_RADIUS_PRECISE_M = 250
COMPLETION_WINDOW_DAYS = 730  # ~2 years - "plausible window before the recurrence"
WARD_LEVEL_SPATIAL_SCORE = 0.6  # fixed, documented - a compatible-ward signal is real
# but weaker evidence than a genuinely close precise distance, never dressed up as one.
COMBINED_THRESHOLD = 0.55
SEMANTIC_WEIGHT = 0.6
SPATIAL_WEIGHT = 0.4


def _parse_embedding(raw) -> np.ndarray:
    return np.array(json.loads(raw)) if isinstance(raw, str) else np.array(raw)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _issue_geom_is_precise(conn, issue_id: int) -> bool:
    """An issue's geom is a centroid of its member reports' points. Only
    trust it as a precise location if every contributing report was itself
    precisely geocoded (confidence 1.0) - a mix of precise and ward-centroid
    reports produces a blended point that isn't precise evidence of anything.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE geom_confidence = 1.0) "
            "FROM reports WHERE issue_id = %s",
            (issue_id,),
        )
        total, precise = cur.fetchone()
    return total > 0 and total == precise


def match_issue_to_work(issue: dict, conn) -> dict | None:
    """ARCHITECTURE.md 5.7: cosine(issue.embedding, work.embedding),
    ST_DWithin(issue.geom, work.geom, radius), completion date within a
    plausible window before the recurrence, same category. Combined score,
    top-1 above threshold, else no match.

    `issue` needs only id and category - everything else (embedding, geom,
    last_reported) is looked up by id so this also works within the same
    uncommitted transaction that just created the issue.

    'other' is excluded on principle, not just absent from the real
    anchors: it's the catch-all bucket for "doesn't fit any of the 8 real
    categories" on both the issue and the work side, so an issue/work pair
    that both landed in 'other' share no actual semantic meaning - matching
    them would be spurious, not a discovered link. (Found via a real
    'other'-to-'other' match in the actual 400-report run before this
    guard existed - not a hypothetical.)
    """
    if issue["category"] == "other":
        return None

    with conn.cursor() as cur:
        cur.execute(
            "SELECT embedding, ward_id, ST_Y(geom), ST_X(geom), last_reported FROM issues WHERE id = %s",
            (issue["id"],),
        )
        row = cur.fetchone()
        if row is None:
            return None
        issue_embedding_raw, issue_ward_id, issue_lat, issue_lon, issue_last_reported = row
        issue_embedding = _parse_embedding(issue_embedding_raw)
        issue_precise = _issue_geom_is_precise(conn, issue["id"])

        cur.execute(
            """
            SELECT id, work_name, geom_confidence, embedding, ward_id,
                   ST_Y(geom), ST_X(geom), completed_on
            FROM works
            WHERE category = %s AND status = 'completed' AND completed_on IS NOT NULL AND geom IS NOT NULL
            """,
            (issue["category"],),
        )
        candidates = cur.fetchall()

    scored = []
    for (work_id, work_name, work_geom_confidence, work_embedding_raw, work_ward_id,
         work_lat, work_lon, completed_on) in candidates:
        if issue_last_reported is None:
            continue
        days_since_completion = (issue_last_reported.date() - completed_on).days
        if days_since_completion < 0 or days_since_completion > COMPLETION_WINDOW_DAYS:
            continue

        semantic_score = _cosine_similarity(issue_embedding, _parse_embedding(work_embedding_raw))
        if semantic_score < SEMANTIC_THRESHOLD:
            continue

        # Only a geocoded landmark (1.0) is a precise point; reviewed-ward and
        # gazetteer-locality points are ward-level evidence (app.ingest.mplads).
        work_precise = work_geom_confidence == 1.0
        distance_m = None
        if issue_precise and work_precise and issue_lat is not None:
            distance_m = _haversine_m(issue_lat, issue_lon, work_lat, work_lon)
            if distance_m > MATCH_RADIUS_PRECISE_M:
                continue
            spatial_score = max(0.0, 1.0 - distance_m / MATCH_RADIUS_PRECISE_M)
            spatial_basis = "precise"
        else:
            if issue_ward_id is None or issue_ward_id != work_ward_id:
                continue
            spatial_score = WARD_LEVEL_SPATIAL_SCORE
            spatial_basis = "ward"

        combined_score = SEMANTIC_WEIGHT * semantic_score + SPATIAL_WEIGHT * spatial_score
        if combined_score < COMBINED_THRESHOLD:
            continue

        if spatial_basis == "precise":
            spatial_evidence = f"{distance_m:.0f}m away (both sides precisely located)"
        else:
            spatial_evidence = (
                f"same ward (#{issue_ward_id}); location precision is ward-level only, "
                "not a precise distance"
            )

        match_reason = (
            f"Issue #{issue['id']} ({issue['category']}) matches work #{work_id} "
            f"('{work_name}'), {spatial_evidence}; work completed {completed_on} "
            f"({days_since_completion} days before the issue's last report); "
            f"semantic similarity {semantic_score:.2f}."
        )

        scored.append({
            "issue_id": issue["id"],
            "work_id": work_id,
            "semantic_score": semantic_score,
            "distance_m": distance_m,
            "days_since_completion": days_since_completion,
            "combined_score": combined_score,
            "match_reason": match_reason,
        })

    if not scored:
        return None
    return max(scored, key=lambda m: m["combined_score"])


def run_matcher(conn=None) -> list[dict]:
    """Runs match_issue_to_work for every open/reopened issue and writes
    every hit to `matches`. Never manufactures a match: an issue with no
    candidate clearing every gate (category, completion status/date,
    semantic threshold, spatial radius or ward match, combined threshold)
    is simply left unmatched.
    """
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, category FROM issues WHERE status IN ('open', 'reopened') ORDER BY id"
            )
            issues = [{"id": r[0], "category": r[1]} for r in cur.fetchall()]

        matches = []
        with conn.cursor() as cur:
            for issue in issues:
                match = match_issue_to_work(issue, conn)
                if match is None:
                    continue
                matches.append(match)
                cur.execute(
                    """
                    INSERT INTO matches (
                        issue_id, work_id, semantic_score, distance_m,
                        days_since_completion, combined_score, match_reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        match["issue_id"], match["work_id"], match["semantic_score"],
                        match["distance_m"], match["days_since_completion"],
                        match["combined_score"], match["match_reason"],
                    ),
                )

        if owns_conn:
            conn.commit()
        return matches
    finally:
        if owns_conn:
            conn.close()
