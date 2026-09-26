import json
import math
from datetime import datetime

from app.db import get_connection

# Priority = w1*Exposure + w2*Severity + w3*Recurrence + w4*TimeOpen
# ARCHITECTURE.md gives no exact w1-w4 values, only that they must be
# explicit, printable constants. Chosen as a weighted average (sums to 1)
# before looking at any real output: severity weighted highest (immediate
# danger), exposure and recurrence next (public-safety amplifier / proof of
# persistent neglect), time-open lowest (a real but secondary signal).
W_EXPOSURE = 0.25
W_SEVERITY = 0.35
W_RECURRENCE = 0.25
W_TIME_OPEN = 0.15

# Published exposure site weights, per ARCHITECTURE.md 5.8 exactly.
SITE_WEIGHTS = {
    "school": 1.0,
    "hospital": 1.0,
    "market": 0.7,
    "water_body": 0.6,
    "bus_stop": 0.5,
}
# "higher for drainage/sewage categories" - a water body near a
# drainage/sewage issue is a real contamination-risk amplifier, treated as
# seriously as a school/hospital. Applies only when the ISSUE is that
# category, not globally.
WATER_BODY_WEIGHT_DRAINAGE = 1.0

# Radius scales inversely with ward population density, per ARCHITECTURE.md
# 5.8. wards.area_sqkm is now filled for all 58 wards, derived from the
# boundary geometry by app/ingest/wards.py (507.1 sq km total against PMC's
# published ~516). wards.population is still NULL everywhere: PMC publishes
# it per ward only inside the final ward map PDFs, and pmc.gov.in was
# unreachable when this was attempted - see data/labelling/ward_population.csv,
# which carries the per-ward source URL and needs only that one column filled.
# Inventing the number would silently reshape every ranking, so until it is
# filled every call falls back to BASE_EXPOSURE_RADIUS_M.
BASE_EXPOSURE_RADIUS_M = 300
REFERENCE_DENSITY_PER_KM2 = 20000  # a plausible dense-urban-ward reference point
MIN_RADIUS_M = 150
MAX_RADIUS_M = 600

SEVERITY_SCORE = {"cosmetic": 0.0, "moderate": 0.5, "critical": 1.0}
_BAND_ORDER = ("cosmetic", "moderate", "critical")

RECURRENCE_NORM_CAP = 3  # 3+ recurrences -> fully saturated recurrence term
TIME_OPEN_NORM_DAYS = 90  # 3 months open -> fully saturated time-open term


def _site_weight(kind: str, issue_category: str) -> float:
    if kind == "water_body" and issue_category == "drainage_sewage":
        return WATER_BODY_WEIGHT_DRAINAGE
    return SITE_WEIGHTS.get(kind, 0.0)


def _exposure_radius(conn, ward_id: int | None) -> float:
    if ward_id is None:
        return BASE_EXPOSURE_RADIUS_M
    with conn.cursor() as cur:
        cur.execute("SELECT population, area_sqkm FROM wards WHERE id = %s", (ward_id,))
        row = cur.fetchone()
    if not row or not row[0] or not row[1]:
        return BASE_EXPOSURE_RADIUS_M
    population, area_sqkm = row
    density = population / area_sqkm
    radius = BASE_EXPOSURE_RADIUS_M * math.sqrt(REFERENCE_DENSITY_PER_KM2 / density)
    return max(MIN_RADIUS_M, min(MAX_RADIUS_M, radius))


def _issue_geom_is_precise(conn, issue_id: int) -> bool:
    """Same rule as app.core.matcher._issue_geom_is_precise: only trust an
    issue's centroid as a real point if every member report was itself
    precisely geocoded. Kept as a local copy rather than importing
    matcher's private helper, to keep this module independent (same
    pattern already used for the small geo helpers duplicated across
    clustering.py/matcher.py/osm_sensitive_sites.py).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE geom_confidence = 1.0) "
            "FROM reports WHERE issue_id = %s",
            (issue_id,),
        )
        total, precise = cur.fetchone()
    return total > 0 and total == precise


def compute_exposure(issue: dict, conn) -> tuple[float, dict]:
    """Exposure = max(weight(kind) : site within radius), per ARCHITECTURE.md
    5.8 - max, not sum, so five bus stops never outrank one hospital.

    Spatial honesty: a real radius-based ST_DWithin check only runs when the
    issue's geometry is precise. For a ward-level issue, "within radius"
    would require trusting a ward-centroid point as if it were the real
    location - instead this checks ward membership only (any sensitive site
    that falls within the same PMC ward), and never reports a distance,
    because none was legitimately measured.
    """
    issue_precise = _issue_geom_is_precise(conn, issue["id"])

    if issue_precise and issue["lat"] is not None:
        radius = _exposure_radius(conn, issue["ward_id"])
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT kind, name,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)
                FROM sensitive_sites
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                    %(radius)s
                )
                """,
                {"lon": issue["lon"], "lat": issue["lat"], "radius": radius},
            )
            rows = cur.fetchall()
        spatial_basis = "precise"
        candidates = [{"kind": k, "name": n, "distance_m": float(d)} for k, n, d in rows]
        radius_reported = radius
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.kind, s.name FROM sensitive_sites s
                WHERE EXISTS (
                    SELECT 1 FROM wards w WHERE w.id = %s AND ST_Contains(w.geom, s.geom)
                )
                """,
                (issue["ward_id"],),
            )
            rows = cur.fetchall()
        spatial_basis = "ward"
        candidates = [{"kind": k, "name": n, "distance_m": None} for k, n in rows]
        radius_reported = None

    if not candidates:
        return 0.0, {
            "spatial_basis": spatial_basis,
            "radius_m": radius_reported,
            "matched_site": None,
            "candidate_count": 0,
        }

    best = max(candidates, key=lambda c: _site_weight(c["kind"], issue["category"]))
    score = _site_weight(best["kind"], issue["category"])
    return score, {
        "spatial_basis": spatial_basis,
        "radius_m": radius_reported,
        "matched_site": best,
        "candidate_count": len(candidates),
    }


def _issue_severity_band(conn, issue_id: int) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT severity FROM reports WHERE issue_id = %s AND severity IS NOT NULL", (issue_id,))
        bands = [r[0] for r in cur.fetchall()]
    if not bands:
        return "cosmetic"
    return max(bands, key=_BAND_ORDER.index)


def compute_priority(issue_id: int, conn) -> tuple[float, dict]:
    """Priority = w1*Exposure + w2*Severity + w3*Recurrence + w4*TimeOpen.
    No model, ever - every term is a deterministic lookup or normalized
    count/duration. Returns (total, full breakdown dict) so the UI (and
    this report) can show every term's working, not just the final number.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT category, ward_id, ST_Y(geom), ST_X(geom), first_reported, "
            "recurrence_count, closed_at FROM issues WHERE id = %s",
            (issue_id,),
        )
        row = cur.fetchone()
    category, ward_id, lat, lon, first_reported, recurrence_count, closed_at = row

    exposure_term, exposure_detail = compute_exposure(
        {"id": issue_id, "category": category, "ward_id": ward_id, "lat": lat, "lon": lon}, conn
    )

    severity_band = _issue_severity_band(conn, issue_id)
    severity_term = SEVERITY_SCORE[severity_band]

    recurrence_term = min(recurrence_count / RECURRENCE_NORM_CAP, 1.0)

    reference_time = closed_at or datetime.now(first_reported.tzinfo)
    time_open_days = (reference_time - first_reported).days
    time_open_term = min(max(time_open_days, 0) / TIME_OPEN_NORM_DAYS, 1.0)

    total = (
        W_EXPOSURE * exposure_term
        + W_SEVERITY * severity_term
        + W_RECURRENCE * recurrence_term
        + W_TIME_OPEN * time_open_term
    )

    exposure_note = (
        f"{exposure_detail['matched_site']['kind']} within {exposure_detail['radius_m']:.0f}m"
        if exposure_detail["matched_site"] and exposure_detail["spatial_basis"] == "precise"
        else f"{exposure_detail['matched_site']['kind']} in the same ward (ward-level precision)"
        if exposure_detail["matched_site"]
        else "no sensitive site found nearby"
    )
    explanation = (
        f"Priority {total:.2f} = {W_EXPOSURE}*exposure({exposure_term:.2f}) + "
        f"{W_SEVERITY}*severity({severity_term:.2f}, '{severity_band}') + "
        f"{W_RECURRENCE}*recurrence({recurrence_term:.2f}, count={recurrence_count}) + "
        f"{W_TIME_OPEN}*time_open({time_open_term:.2f}, {time_open_days}d open). "
        f"Exposure basis: {exposure_note}."
    )

    breakdown = {
        "total": total,
        "weights": {
            "exposure": W_EXPOSURE, "severity": W_SEVERITY,
            "recurrence": W_RECURRENCE, "time_open": W_TIME_OPEN,
        },
        "terms": {
            "exposure": exposure_term, "severity": severity_term,
            "recurrence": recurrence_term, "time_open": time_open_term,
        },
        "exposure_detail": exposure_detail,
        "severity_band": severity_band,
        "recurrence_count": recurrence_count,
        "time_open_days": time_open_days,
        "explanation": explanation,
    }
    return total, breakdown


def run_priority(conn=None) -> int:
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM issues ORDER BY id")
            issue_ids = [r[0] for r in cur.fetchall()]

        for issue_id in issue_ids:
            total, breakdown = compute_priority(issue_id, conn)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE issues SET priority_score = %s, priority_breakdown = %s::jsonb WHERE id = %s",
                    (total, json.dumps(breakdown), issue_id),
                )

        if owns_conn:
            conn.commit()
        return len(issue_ids)
    finally:
        if owns_conn:
            conn.close()
