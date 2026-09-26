import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from app.api.schemas import (
    FeedbackCreateRequest,
    FeedbackCreateResponse,
    FeedbackSummary,
    GeoPoint,
    HealthResponse,
    IssueCloseResponse,
    IssueDetailResponse,
    IssueListResponse,
    IssueRouteResponse,
    IssueSummary,
    MapIssuePoint,
    MapResponse,
    MapSitePoint,
    MapWard,
    MapWorkPoint,
    MatchSummary,
    MetricsResponse,
    PhotoUploadResponse,
    ReportCreateRequest,
    ReportCreateResponse,
    ReportInIssue,
    SignalSummary,
    StatsResponse,
    WorkSummary,
)
from app.core.clustering import COSINE_THRESHOLD, spatial_ok
from app.core.matcher import match_issue_to_work
from app.core.metrics import compute_metrics
from app.core.priority import compute_priority
from app.core.recurrence import run_recurrence_check
from app.core.routing import route_issue
from app.core.signals import run_signals
from app.db import get_connection
from app.ingest.location import extract_ward_number
from app.nlp.classify import classify
from app.nlp.embeddings import get_embedding_model as _get_embedding_model
from app.nlp.language import detect_language
from app.nlp.location import resolve_report_location
from app.nlp.photo_severity import estimate_photo_severity
from app.nlp.photo_validate import process_upload, read_photo, write_photo
from app.nlp.severity import BAND_ORDER, severity
from app.nlp.translate import translate_to_english

# Gitignored, and deliberately not mounted as static files: photos are only
# reachable through serve_photo, which decrypts and checks the DB first.
UPLOAD_DIR = Path("data/uploads")
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Phone camera JPEGs (12-48 MP) routinely exceed 5 MB; they are downscaled to
# 2048 px before storage, so this limit only bounds the request.
MAX_PHOTO_BYTES = 20 * 1024 * 1024

app = FastAPI(title="CivicFix API")

# Local-dev only: lets a Vite dev server (a different origin/port) call
# this API. Regex, not a fixed port, since Vite auto-increments its port
# when the default is already taken by another concurrent dev server on
# this shared machine. No auth exists yet either way - not a production
# CORS policy.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)



def _parse_embedding(raw) -> np.ndarray:
    return np.array(json.loads(raw)) if isinstance(raw, str) else np.array(raw)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _time_ok(reported_at_a: datetime, reported_at_b: datetime, window_days: int = 7) -> bool:
    return abs((reported_at_a - reported_at_b).days) <= window_days


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _location_precision_from_breakdown(breakdown: Optional[dict]) -> str:
    if not breakdown:
        return "unknown"
    basis = (breakdown.get("exposure_detail") or {}).get("spatial_basis")
    if basis == "precise":
        return "precise"
    if basis == "ward":
        return "ward_level"
    return "unknown"


def _work_location_precision(description: Optional[str]) -> str:
    """Works has no stored precision column - re-derives it the same way
    app.core.matcher._work_geom_is_precise does: a ward-number mention in
    the description means the point is a ward centroid, not geocoded.
    """
    return "ward_level" if extract_ward_number(description) is not None else "precise"


def _synthetic_flags_for_issues(conn, issue_ids: list[int]) -> dict[int, bool]:
    if not issue_ids:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT issue_id, bool_and(is_synthetic) AS all_synthetic FROM reports "
            "WHERE issue_id = ANY(%s) GROUP BY issue_id",
            (issue_ids,),
        )
        return {r["issue_id"]: r["all_synthetic"] for r in cur.fetchall()}


def _issue_summary_from_row(r: dict, is_synthetic: Optional[bool]) -> IssueSummary:
    return IssueSummary(
        issue_id=r["id"], category=r["category"], ward_id=r["ward_id"], report_count=r["report_count"],
        first_reported=r["first_reported"], last_reported=r["last_reported"], status=r["status"],
        recurrence_count=r["recurrence_count"], priority_score=r["priority_score"],
        priority_breakdown=r["priority_breakdown"],
        location=GeoPoint(lat=r["lat"], lon=r["lon"]) if r["lat"] is not None else None,
        location_precision=_location_precision_from_breakdown(r["priority_breakdown"]),
        is_synthetic=is_synthetic if is_synthetic is not None else True,
        routed_agency=r.get("routed_agency"), routed_at=r.get("routed_at"),
    )


def _work_summary_from_row(r: dict) -> WorkSummary:
    return WorkSummary(
        work_id=r["work_id"], work_name=r["work_name"], description=r["description"], category=r["category"],
        status=r["status"], cost=float(r["cost"]) if r["cost"] is not None else None,
        completed_on=r["completed_on"], agency=r["agency"], ward_id=r["ward_id"],
        location=GeoPoint(lat=r["lat"], lon=r["lon"]) if r["lat"] is not None else None,
        location_precision=_work_location_precision(r["description"]) if r["lat"] is not None else None,
    )


def _match_summary_from_row(r: dict, issue_location_precision: str) -> MatchSummary:
    work = WorkSummary(
        work_id=r["work_id"], work_name=r["work_name"], description=r["description"], category=r["work_category"],
        status=r["work_status"], cost=float(r["cost"]) if r["cost"] is not None else None,
        completed_on=r["completed_on"], agency=r["agency"], ward_id=r["work_ward_id"],
        location=GeoPoint(lat=r["work_lat"], lon=r["work_lon"]) if r["work_lat"] is not None else None,
        location_precision=_work_location_precision(r["description"]) if r["work_lat"] is not None else None,
    )
    return MatchSummary(
        match_id=r["match_id"], issue_id=r["issue_id"], work_id=r["work_id"], category=r["work_category"],
        semantic_score=r["semantic_score"], combined_score=r["combined_score"], distance_m=r["distance_m"],
        days_since_completion=r["days_since_completion"], match_reason=r["match_reason"],
        issue_location_precision=issue_location_precision, work=work,
    )


MATCH_JOIN_SQL = """
    SELECT m.id AS match_id, m.issue_id, m.work_id, m.semantic_score, m.combined_score,
           m.distance_m, m.days_since_completion, m.match_reason,
           w.work_name, w.description, w.category AS work_category, w.status AS work_status,
           w.cost, w.completed_on, w.agency, w.ward_id AS work_ward_id,
           ST_Y(w.geom) AS work_lat, ST_X(w.geom) AS work_lon
    FROM matches m JOIN works w ON w.id = m.work_id
"""


@app.get("/api/health", response_model=HealthResponse)
def health():
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                counts = {}
                for table in ("works", "reports", "issues"):
                    cur.execute(f"SELECT count(*) FROM {table}")
                    counts[table] = cur.fetchone()[0]
            return HealthResponse(status="ok", database_connected=True, counts=counts)
        finally:
            conn.close()
    except Exception:
        return HealthResponse(status="degraded", database_connected=False, counts={})


@app.get("/api/stats", response_model=StatsResponse)
def stats(db=Depends(get_db)):
    counts = {}
    with db.cursor() as cur:
        for table, key in [
            ("wards", "wards"), ("works", "works"), ("reports", "reports"), ("issues", "issues"),
            ("matches", "matches"), ("sensitive_sites", "sensitive_sites"), ("signals", "verification_signals"),
        ]:
            cur.execute(f"SELECT count(*) FROM {table}")
            counts[key] = cur.fetchone()[0]
    return StatsResponse(**counts)


@app.get("/api/metrics", response_model=MetricsResponse)
def metrics(db=Depends(get_db)):
    """Real evaluation numbers per ARCHITECTURE.md section 6 - computed
    from the actual database plus a persisted offline classifier
    evaluation, never asserted. See app/core/metrics.py for the two
    honest simplifications (no dedup ground truth exists; location
    reports the real pipeline's outcome, not a separate baseline run).
    """
    return MetricsResponse(**compute_metrics(conn=db))


@app.post("/api/issues/{issue_id}/close", response_model=IssueCloseResponse)
def close_issue(issue_id: int, db=Depends(get_db)):
    """Administrator action: marks an issue resolved. This is what makes
    recurrence.py's precondition (a prior CLOSED issue) reachable at all -
    nothing else in this system ever closes an issue. If a new report
    later matches this issue's ward+category+timing, run_recurrence_check
    (called from POST /api/reports) will reopen it automatically.
    """
    with db.cursor() as cur:
        cur.execute("SELECT status FROM issues WHERE id = %s", (issue_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
    if row[0] == "closed":
        raise HTTPException(status_code=400, detail=f"issue {issue_id} is already closed")

    with db.cursor() as cur:
        cur.execute(
            "UPDATE issues SET status = 'closed', closed_at = now() WHERE id = %s "
            "RETURNING status, closed_at",
            (issue_id,),
        )
        status, closed_at = cur.fetchone()
    db.commit()
    return IssueCloseResponse(issue_id=issue_id, status=status, closed_at=closed_at)


@app.post("/api/issues/{issue_id}/route", response_model=IssueRouteResponse)
def route_issue_endpoint(issue_id: int, db=Depends(get_db)):
    """Deterministic work-order routing: looks up the issue's category in
    app.core.routing's fixed table (never invented per-issue) and records
    a signal citing exactly which rule fired, matching every other
    verification signal's source-record convention."""
    with db.cursor() as cur:
        cur.execute("SELECT category, routed_agency FROM issues WHERE id = %s", (issue_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
    category, existing_agency = row
    if existing_agency is not None:
        raise HTTPException(status_code=400, detail=f"issue {issue_id} is already routed to {existing_agency}")

    agency = route_issue(category)
    with db.cursor() as cur:
        cur.execute(
            "UPDATE issues SET routed_agency = %s, routed_at = now() WHERE id = %s "
            "RETURNING routed_agency, routed_at",
            (agency, issue_id),
        )
        routed_agency, routed_at = cur.fetchone()
        cur.execute(
            "INSERT INTO signals (issue_id, rule_name, explanation, source_record_ids) "
            "VALUES (%s, 'ROUTED_TO_AGENCY', %s, %s::jsonb)",
            (
                issue_id,
                f"Issue #{issue_id} (category: {category}) routed to {routed_agency} per the fixed "
                f"category-to-agency table.",
                json.dumps({"issue_id": issue_id, "category": category}),
            ),
        )
    db.commit()
    return IssueRouteResponse(issue_id=issue_id, routed_agency=routed_agency, routed_at=routed_at)


@app.post("/api/issues/{issue_id}/feedback", response_model=FeedbackCreateResponse, status_code=201)
def submit_feedback(issue_id: int, payload: FeedbackCreateRequest, db=Depends(get_db)):
    """Closes the loop after resolution: a citizen confirms the fix or
    disputes it. A dispute reopens the issue directly (status -> reopened,
    recurrence_count + 1) - simpler and more precise than routing through
    run_recurrence_check's category/ward/proximity matching, since we
    already know exactly which issue this feedback is about.
    """
    with db.cursor() as cur:
        cur.execute("SELECT status FROM issues WHERE id = %s", (issue_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
    if row[0] != "closed":
        raise HTTPException(
            status_code=400,
            detail=f"issue {issue_id} is not closed (status: {row[0]}) - feedback only applies after closure",
        )

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (issue_id, resolved_confirmed, comment, submitted_at, is_synthetic) "
            "VALUES (%s, %s, %s, now(), true) "
            "RETURNING id, issue_id, resolved_confirmed, comment, submitted_at, is_synthetic",
            (issue_id, payload.resolved_confirmed, payload.comment),
        )
        fb_id, fb_issue_id, resolved_confirmed, comment, submitted_at, is_synthetic = cur.fetchone()

        if payload.resolved_confirmed:
            issue_status = "closed"
        else:
            cur.execute(
                "UPDATE issues SET status = 'reopened', recurrence_count = recurrence_count + 1, "
                "closed_at = NULL WHERE id = %s RETURNING status",
                (issue_id,),
            )
            issue_status = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO signals (issue_id, rule_name, explanation, source_record_ids) "
                "VALUES (%s, 'CITIZEN_DISPUTED_RESOLUTION', %s, %s::jsonb)",
                (
                    issue_id,
                    f"A citizen reported issue #{issue_id} is not actually resolved (feedback #{fb_id}); "
                    f"reopened for review.",
                    json.dumps({"issue_id": issue_id, "feedback_id": fb_id}),
                ),
            )
    db.commit()
    return FeedbackCreateResponse(
        feedback=FeedbackSummary(
            feedback_id=fb_id, issue_id=fb_issue_id, resolved_confirmed=resolved_confirmed,
            comment=comment, submitted_at=submitted_at, is_synthetic=is_synthetic,
        ),
        issue_status=issue_status,
    )


@app.get("/api/issues", response_model=IssueListResponse)
def list_issues(
    ward_id: Optional[int] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    min_priority: Optional[float] = None,
    sort: str = Query("priority", pattern="^(priority|recent)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    order_sql = (
        "last_reported DESC NULLS LAST, id DESC" if sort == "recent"
        else "priority_score DESC NULLS LAST, id"
    )
    where, params = [], {}
    if ward_id is not None:
        where.append("ward_id = %(ward_id)s")
        params["ward_id"] = ward_id
    if category is not None:
        where.append("category = %(category)s")
        params["category"] = category
    if status is not None:
        where.append("status = %(status)s")
        params["status"] = status
    if min_priority is not None:
        where.append("priority_score >= %(min_priority)s")
        params["min_priority"] = min_priority
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT count(*) AS n FROM issues {where_sql}", params)
        total = cur.fetchone()["n"]

        cur.execute(
            f"""
            SELECT id, category, ward_id, report_count, first_reported, last_reported, status,
                   recurrence_count, priority_score, priority_breakdown, ST_Y(geom) AS lat, ST_X(geom) AS lon,
                   routed_agency, routed_at
            FROM issues {where_sql}
            ORDER BY {order_sql}
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**params, "limit": limit, "offset": offset},
        )
        rows = cur.fetchall()

    synthetic_map = _synthetic_flags_for_issues(db, [r["id"] for r in rows])
    items = [_issue_summary_from_row(r, synthetic_map.get(r["id"])) for r in rows]
    return IssueListResponse(total=total, limit=limit, offset=offset, items=items)


@app.get("/api/issues/{issue_id}", response_model=IssueDetailResponse)
def issue_detail(issue_id: int, db=Depends(get_db)):
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, category, ward_id, status, report_count, first_reported, last_reported, "
            "recurrence_count, priority_score, priority_breakdown, ST_Y(geom) AS lat, ST_X(geom) AS lon, "
            "routed_agency, routed_at "
            "FROM issues WHERE id = %s",
            (issue_id,),
        )
        issue_row = cur.fetchone()
    if issue_row is None:
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")

    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, raw_text, reported_at, category, category_conf, severity, location_phrase, "
            "geom_confidence, ward_id, is_synthetic, photo_url, language, translated_text, "
            "photo_severity_score, photo_severity_band, photo_checks "
            "FROM reports WHERE issue_id = %s ORDER BY reported_at",
            (issue_id,),
        )
        report_rows = cur.fetchall()

        cur.execute(f"{MATCH_JOIN_SQL} WHERE m.issue_id = %s", (issue_id,))
        match_rows = cur.fetchall()

        cur.execute(
            "SELECT id, issue_id, match_id, rule_name, explanation, source_record_ids "
            "FROM signals WHERE issue_id = %s",
            (issue_id,),
        )
        signal_rows = cur.fetchall()

        cur.execute(
            "SELECT id, issue_id, resolved_confirmed, comment, submitted_at, is_synthetic "
            "FROM feedback WHERE issue_id = %s ORDER BY submitted_at",
            (issue_id,),
        )
        feedback_rows = cur.fetchall()

    is_synthetic = all(r["is_synthetic"] for r in report_rows) if report_rows else True
    location_precision = _location_precision_from_breakdown(issue_row["priority_breakdown"])

    return IssueDetailResponse(
        issue_id=issue_row["id"], category=issue_row["category"], ward_id=issue_row["ward_id"],
        status=issue_row["status"], report_count=issue_row["report_count"],
        first_reported=issue_row["first_reported"], last_reported=issue_row["last_reported"],
        recurrence_count=issue_row["recurrence_count"],
        location=GeoPoint(lat=issue_row["lat"], lon=issue_row["lon"]) if issue_row["lat"] is not None else None,
        location_precision=location_precision,
        is_synthetic=is_synthetic,
        priority_score=issue_row["priority_score"], priority_breakdown=issue_row["priority_breakdown"],
        reports=[ReportInIssue(**r) for r in report_rows],
        matches=[_match_summary_from_row(r, location_precision) for r in match_rows],
        signals=[
            SignalSummary(signal_id=r["id"], issue_id=r["issue_id"], match_id=r["match_id"],
                           rule_name=r["rule_name"], explanation=r["explanation"],
                           source_record_ids=r["source_record_ids"])
            for r in signal_rows
        ],
        feedback=[
            FeedbackSummary(feedback_id=r["id"], issue_id=r["issue_id"], resolved_confirmed=r["resolved_confirmed"],
                             comment=r["comment"], submitted_at=r["submitted_at"], is_synthetic=r["is_synthetic"])
            for r in feedback_rows
        ],
        routed_agency=issue_row["routed_agency"], routed_at=issue_row["routed_at"],
    )


@app.get("/api/matches", response_model=list[MatchSummary])
def list_matches(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db=Depends(get_db)):
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"{MATCH_JOIN_SQL} JOIN issues i ON i.id = m.issue_id "
            "ORDER BY m.combined_score DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        rows = cur.fetchall()
        issue_ids = [r["issue_id"] for r in rows]
        breakdowns = {}
        if issue_ids:
            cur.execute("SELECT id, priority_breakdown FROM issues WHERE id = ANY(%s)", (issue_ids,))
            breakdowns = {r["id"]: r["priority_breakdown"] for r in cur.fetchall()}

    return [
        _match_summary_from_row(r, _location_precision_from_breakdown(breakdowns.get(r["issue_id"])))
        for r in rows
    ]


@app.get("/api/works", response_model=list[WorkSummary])
def list_works(
    ward_id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    where, params = [], {}
    if ward_id is not None:
        where.append("ward_id = %(ward_id)s")
        params["ward_id"] = ward_id
    if category is not None:
        where.append("category = %(category)s")
        params["category"] = category
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT id AS work_id, work_name, description, category, status, cost, completed_on, agency,
                   ward_id, ST_Y(geom) AS lat, ST_X(geom) AS lon
            FROM works {where_sql} ORDER BY id LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**params, "limit": limit, "offset": offset},
        )
        rows = cur.fetchall()
    return [_work_summary_from_row(r) for r in rows]


@app.get("/api/map", response_model=MapResponse)
def map_data(db=Depends(get_db)):
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, category, status, priority_score, priority_breakdown, "
            "ST_Y(geom) AS lat, ST_X(geom) AS lon FROM issues WHERE geom IS NOT NULL"
        )
        issue_rows = cur.fetchall()

        cur.execute(
            "SELECT DISTINCT w.id AS work_id, w.category, w.work_name, w.description, "
            "ST_Y(w.geom) AS lat, ST_X(w.geom) AS lon "
            "FROM works w JOIN matches m ON m.work_id = w.id WHERE w.geom IS NOT NULL"
        )
        work_rows = cur.fetchall()

        cur.execute("SELECT id, kind, name, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM sensitive_sites")
        site_rows = cur.fetchall()

        cur.execute("SELECT id, name FROM wards ORDER BY id")
        ward_rows = cur.fetchall()

    return MapResponse(
        issues=[
            MapIssuePoint(issue_id=r["id"], category=r["category"], status=r["status"],
                          priority_score=r["priority_score"], location=GeoPoint(lat=r["lat"], lon=r["lon"]),
                          location_precision=_location_precision_from_breakdown(r["priority_breakdown"]))
            for r in issue_rows
        ],
        matched_works=[
            MapWorkPoint(work_id=r["work_id"], category=r["category"], work_name=r["work_name"],
                        location=GeoPoint(lat=r["lat"], lon=r["lon"]),
                        location_precision=_work_location_precision(r["description"]))
            for r in work_rows
        ],
        sensitive_sites=[
            MapSitePoint(site_id=r["id"], kind=r["kind"], location=GeoPoint(lat=r["lat"], lon=r["lon"]))
            for r in site_rows
        ],
        wards=[MapWard(ward_id=r["id"], name=r["name"]) for r in ward_rows],
    )


def _issue_geom_confidence_proxy(conn, issue_id: int) -> float:
    """Same semantics as app.core.matcher._issue_geom_is_precise, expressed
    as the 1.0/0.4 confidence value app.core.clustering.spatial_ok expects.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE geom_confidence = 1.0) FROM reports WHERE issue_id = %s",
            (issue_id,),
        )
        total, precise = cur.fetchone()
    return 1.0 if total > 0 and total == precise else 0.4


def _create_issue_from_report(conn, report: dict) -> int:
    geom_expr = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)" if report["lat"] is not None else "NULL"
    embedding_literal = "[" + ",".join(str(float(v)) for v in report["embedding"]) + "]"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO issues (category, geom, ward_id, first_reported, last_reported, report_count, status, embedding)
            VALUES (%(category)s, {geom_expr}, %(ward_id)s, %(reported_at)s, %(reported_at)s, 1, 'open', %(embedding)s::vector)
            RETURNING id
            """,
            {
                "category": report["category"], "lat": report["lat"], "lon": report["lon"],
                "ward_id": report["ward_id"], "reported_at": report["reported_at"],
                "embedding": embedding_literal,
            },
        )
        return cur.fetchone()[0]


def _attach_or_create_issue(conn, report: dict) -> tuple[int, bool]:
    """Live-add version of clustering: checks this ONE new report against
    EXISTING open/reopened issues using the exact same rules as
    app.core.clustering.cluster_reports (same category, spatial_ok, 7-day
    window, cosine >= 0.82), reusing that module's own spatial_ok and
    threshold rather than reimplementing the rule. Deliberately does not
    call the batch run_clustering()/run_matcher() orchestration functions:
    a full re-cluster would reassign every issue id on every single live
    add (disruptive for a demo where issue ids are shown/clicked), and
    run_matcher() has no delete-before-insert (would duplicate every
    existing match row on repeated calls - a real bug that would corrupt
    this endpoint's very first target audience, since DEMO.md explicitly
    expects it to be callable more than once). Neither of those files is
    modified; this only calls their pure per-item functions.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, embedding, ward_id, ST_Y(geom) AS lat, ST_X(geom) AS lon, last_reported "
            "FROM issues WHERE category = %s AND status IN ('open', 'reopened')",
            (report["category"],),
        )
        candidates = cur.fetchall()

    best_issue_id, best_sim = None, -1.0
    for c in candidates:
        if report["lat"] is None or c["lat"] is None:
            if report["ward_id"] is None or c["ward_id"] is None or report["ward_id"] != c["ward_id"]:
                continue
        else:
            issue_like = {
                "lat": c["lat"], "lon": c["lon"],
                "geom_confidence": _issue_geom_confidence_proxy(conn, c["id"]),
                "ward_id": c["ward_id"],
            }
            report_like = {
                "lat": report["lat"], "lon": report["lon"],
                "geom_confidence": report["geom_confidence"] or 0.0,
                "ward_id": report["ward_id"],
            }
            if not spatial_ok(report_like, issue_like):
                continue
        if not _time_ok(report["reported_at"], c["last_reported"]):
            continue
        sim = _cosine_similarity(report["embedding"], _parse_embedding(c["embedding"]))
        if sim >= COSINE_THRESHOLD and sim > best_sim:
            best_sim, best_issue_id = sim, c["id"]

    if best_issue_id is not None:
        return best_issue_id, True
    return _create_issue_from_report(conn, report), False


def _recompute_issue_aggregates(conn, issue_id: int) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, embedding, reported_at "
            "FROM reports WHERE issue_id = %s",
            (issue_id,),
        )
        members = cur.fetchall()

    lats = [m["lat"] for m in members if m["lat"] is not None]
    lons = [m["lon"] for m in members if m["lon"] is not None]
    embeddings = [_parse_embedding(m["embedding"]) for m in members if m["embedding"] is not None]
    reported_ats = [m["reported_at"] for m in members]

    geom_expr = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)" if lats else "NULL"
    embedding_literal = None
    if embeddings:
        embedding_literal = "[" + ",".join(str(float(v)) for v in np.mean(embeddings, axis=0)) + "]"

    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE issues SET
                report_count = %(report_count)s,
                first_reported = %(min_reported)s,
                last_reported = %(max_reported)s,
                geom = {geom_expr},
                embedding = COALESCE(%(embedding)s::vector, embedding)
            WHERE id = %(issue_id)s
            """,
            {
                "report_count": len(members), "min_reported": min(reported_ats), "max_reported": max(reported_ats),
                "lat": sum(lats) / len(lats) if lats else None, "lon": sum(lons) / len(lons) if lons else None,
                "embedding": embedding_literal, "issue_id": issue_id,
            },
        )


def _refresh_match_for_issue(conn, issue_id: int) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT category FROM issues WHERE id = %s", (issue_id,))
        category = cur.fetchone()[0]

    match = match_issue_to_work({"id": issue_id, "category": category}, conn)
    with conn.cursor() as cur:
        # A signal from a PRIOR call to this function can already reference
        # this issue's current match row (match_id FK) - e.g. any report
        # that joins or merges into an already-matched issue hits this.
        # run_signals() (called right after this, in create_report) rebuilds
        # signals from scratch anyway, so deleting them here first is safe,
        # not a loss - discovered live: a new report attaching to issue #24
        # (already matched + signalled) crashed here with a FK violation
        # before this fix.
        cur.execute(
            "DELETE FROM signals WHERE match_id IN (SELECT id FROM matches WHERE issue_id = %s)",
            (issue_id,),
        )
        cur.execute("DELETE FROM matches WHERE issue_id = %s", (issue_id,))
        if match:
            cur.execute(
                "INSERT INTO matches (issue_id, work_id, semantic_score, distance_m, days_since_completion, "
                "combined_score, match_reason) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (match["issue_id"], match["work_id"], match["semantic_score"], match["distance_m"],
                 match["days_since_completion"], match["combined_score"], match["match_reason"]),
            )
            match["id"] = cur.fetchone()[0]
    return match


@app.post("/api/uploads/photo", response_model=PhotoUploadResponse, status_code=201)
async def upload_photo(file: UploadFile = File(...), db=Depends(get_db)):
    """Evidence intake. Signals are read from the original bytes, then only a
    re-encoded, metadata-free, upright JPEG is written (encrypted when
    PHOTO_ENCRYPTION_KEY is set). Suspicious signals never reject the
    upload; they are stored and shown to the human reviewer."""
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported content type: {file.content_type}")

    body = await file.read()
    if len(body) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail=f"photo exceeds {MAX_PHOTO_BYTES // (1024 * 1024)}MB limit")

    try:
        clean, checks = process_upload(body, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    del body

    filename = f"{uuid.uuid4().hex}.jpg"
    checks["stored_encrypted"] = write_photo(UPLOAD_DIR / filename, clean)
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO photo_uploads (filename, checks) VALUES (%s, %s::jsonb)",
            (filename, json.dumps(checks)),
        )
    db.commit()
    return PhotoUploadResponse(photo_url=f"/api/photos/{filename}", photo_checks=checks)


PHOTO_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
PHOTO_MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@app.get("/api/photos/{filename}")
@app.get("/uploads/{filename}")  # photo_url format used before 2026-09-27; rows still reference it
def serve_photo(filename: str, db=Depends(get_db)):
    """Serves a photo only once it is attached to a report, decrypting it in
    memory. A guessed or leaked filename of an unattached upload gets 404."""
    match = PHOTO_FILENAME_RE.match(filename)
    if match is None:
        raise HTTPException(status_code=400, detail="invalid filename")

    with db.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM reports WHERE photo_url IN (%s, %s)",
            (f"/api/photos/{filename}", f"/uploads/{filename}"),
        )
        attached = cur.fetchone() is not None
    photo_path = UPLOAD_DIR / filename
    if not attached or not photo_path.is_file():
        raise HTTPException(status_code=404, detail="photo not found")

    try:
        content = read_photo(photo_path)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return Response(content=content, media_type=PHOTO_MEDIA_TYPES[match.group(1)])


@app.post("/api/reports", response_model=ReportCreateResponse, status_code=201)
def create_report(payload: ReportCreateRequest, db=Depends(get_db)):
    """Live citizen-complaint flow: classify -> location -> severity ->
    attach-or-create issue -> recurrence check -> matcher -> priority ->
    signals, using the existing, unmodified pipeline functions throughout.
    Marked is_synthetic=true since this is the prototype's demo endpoint,
    not a production citizen-facing intake.
    """
    if payload.ward_id is not None:
        with db.cursor() as cur:
            cur.execute("SELECT 1 FROM wards WHERE id = %s", (payload.ward_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=400, detail=f"ward_id {payload.ward_id} does not exist")

    # Non-English text is translated before running the (English-only)
    # pipeline, so a Hindi/Marathi complaint gets a real category instead of
    # falling into "other" - see app/nlp/translate.py. Translation failure
    # (unsupported language, or the free translation service being down)
    # degrades to running the pipeline on the original text, same as before.
    language = detect_language(payload.raw_text)
    translated_text = translate_to_english(payload.raw_text, language) if language and language != "en" else None
    pipeline_text = translated_text or payload.raw_text

    # The fine-tuned encoder reads Hindi/Marathi/romanized/code-mixed text
    # directly, so category and embedding use the original words. Location
    # still uses the English translation until the gazetteer covers
    # Hindi/Marathi.
    category, category_conf = classify(payload.raw_text)
    # Severity reads BOTH the original and the translation, and takes the
    # stronger band. The keyword list now carries Marathi/Hindi/romanized
    # entries, so the original must be scored directly: translating first lost
    # real hazards, because the translator renders विजेचा धक्का as "electric
    # shock" and उघड्या तारा as "open wires", neither of which is a keyword,
    # so an electrocution report scored cosmetic. The translation is still
    # scored too - it is the only cover for a language the keyword list has no
    # entries for at all.
    severity_band = max(
        severity(payload.raw_text, category),
        severity(pipeline_text, category),
        key=BAND_ORDER.index,
    )
    lat, lon, geom_conf, ward_id, location_phrase = resolve_report_location(pipeline_text, conn=db)

    # Photo severity: a deterministic formula over the uploaded image's
    # pixels (see app/nlp/photo_severity.py), stored and shown to the
    # reviewer as evidence only. It never changes severity_band, so it
    # never changes priority: a dark or shadowy photo would otherwise read
    # as "critical" and push an issue up the queue.
    photo_severity_score = None
    photo_severity_band = None
    photo_checks = None
    if payload.photo_url:
        photo_filename = Path(payload.photo_url).name
        try:
            result = estimate_photo_severity(read_photo(UPLOAD_DIR / photo_filename))
            photo_severity_score, photo_severity_band = result["score"], result["band"]
        except (ValueError, OSError):
            pass  # undecodable/missing photo - no photo evidence score
        with db.cursor() as cur:
            cur.execute("SELECT checks FROM photo_uploads WHERE filename = %s", (photo_filename,))
            row = cur.fetchone()
        # None for photos uploaded before intake checks existed - shown as "not checked".
        photo_checks = row[0] if row else None

    # Only fills in a location the pipeline itself couldn't find - never
    # overrides a pipeline result, and never turns a ward selection into a
    # fabricated precise point (still ward-centroid confidence 0.4).
    if lat is None and payload.ward_id is not None:
        with db.cursor() as cur:
            cur.execute(
                "SELECT ST_Y(ST_Centroid(geom)), ST_X(ST_Centroid(geom)) FROM wards WHERE id = %s",
                (payload.ward_id,),
            )
            row = cur.fetchone()
        if row:
            lat, lon = row
            geom_conf = 0.4
            ward_id = payload.ward_id

    embedding = _get_embedding_model().encode([payload.raw_text], show_progress_bar=False)[0]
    embedding_literal = "[" + ",".join(str(float(v)) for v in embedding) + "]"
    # timestamptz columns round-trip as timezone-aware datetimes; datetime.now()
    # alone is naive and can't be subtracted from them (_time_ok does exactly
    # that against existing issues' last_reported).
    reported_at = datetime.now().astimezone()
    geom_expr = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)" if lat is not None else "NULL"

    with db.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO reports (raw_text, reported_at, category, category_conf, severity,
                                  location_phrase, geom, geom_confidence, ward_id, embedding, is_synthetic,
                                  photo_url, language, translated_text, photo_severity_score, photo_severity_band,
                                  photo_checks)
            VALUES (%(raw_text)s, %(reported_at)s, %(category)s, %(category_conf)s, %(severity)s,
                    %(location_phrase)s, {geom_expr}, %(geom_conf)s, %(ward_id)s, %(embedding)s::vector, true,
                    %(photo_url)s, %(language)s, %(translated_text)s, %(photo_severity_score)s,
                    %(photo_severity_band)s, %(photo_checks)s::jsonb)
            RETURNING id
            """,
            {
                "raw_text": payload.raw_text, "reported_at": reported_at, "category": category,
                "category_conf": category_conf, "severity": severity_band, "location_phrase": location_phrase,
                "lat": lat, "lon": lon, "geom_conf": geom_conf, "ward_id": ward_id,
                "embedding": embedding_literal, "photo_url": payload.photo_url, "language": language,
                "translated_text": translated_text, "photo_severity_score": photo_severity_score,
                "photo_severity_band": photo_severity_band,
                "photo_checks": json.dumps(photo_checks) if photo_checks is not None else None,
            },
        )
        report_id = cur.fetchone()[0]

    report_dict = {
        "category": category, "geom_confidence": geom_conf, "ward_id": ward_id,
        "lat": lat, "lon": lon, "reported_at": reported_at, "embedding": embedding,
    }
    issue_id, joined_existing = _attach_or_create_issue(db, report_dict)

    with db.cursor() as cur:
        cur.execute("UPDATE reports SET issue_id = %s WHERE id = %s", (issue_id, report_id))

    if joined_existing:
        _recompute_issue_aggregates(db, issue_id)

    run_recurrence_check(conn=db)  # existing, unmodified; a no-op unless a prior CLOSED issue exists

    with db.cursor() as cur:
        cur.execute("SELECT issue_id FROM reports WHERE id = %s", (report_id,))
        issue_id = cur.fetchone()[0]  # may have changed if recurrence merged it into a reopened issue

    match = _refresh_match_for_issue(db, issue_id)
    total, breakdown = compute_priority(issue_id, db)
    with db.cursor() as cur:
        cur.execute(
            "UPDATE issues SET priority_score = %s, priority_breakdown = %s::jsonb WHERE id = %s",
            (total, json.dumps(breakdown), issue_id),
        )

    run_signals(conn=db)  # existing, unmodified; rebuilds from the current matches table
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, issue_id, match_id, rule_name, explanation, source_record_ids "
            "FROM signals WHERE issue_id = %s",
            (issue_id,),
        )
        signal_rows = cur.fetchall()

    match_summary = None
    if match:
        with db.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT work_name, description, category, status, cost, completed_on, agency, ward_id, "
                "ST_Y(geom) AS lat, ST_X(geom) AS lon FROM works WHERE id = %s",
                (match["work_id"],),
            )
            w = cur.fetchone()
        match_summary = MatchSummary(
            match_id=match["id"], issue_id=issue_id, work_id=match["work_id"], category=w["category"],
            semantic_score=match["semantic_score"], combined_score=match["combined_score"],
            distance_m=match["distance_m"], days_since_completion=match["days_since_completion"],
            match_reason=match["match_reason"], issue_location_precision=_location_precision_from_breakdown(breakdown),
            work=WorkSummary(
                work_id=match["work_id"], work_name=w["work_name"], description=w["description"],
                category=w["category"], status=w["status"], cost=float(w["cost"]) if w["cost"] is not None else None,
                completed_on=w["completed_on"], agency=w["agency"], ward_id=w["ward_id"],
                location=GeoPoint(lat=w["lat"], lon=w["lon"]) if w["lat"] is not None else None,
                location_precision=_work_location_precision(w["description"]) if w["lat"] is not None else None,
            ),
        )

    db.commit()

    return ReportCreateResponse(
        report=ReportInIssue(
            id=report_id, raw_text=payload.raw_text, reported_at=reported_at, category=category,
            category_conf=category_conf, severity=severity_band, location_phrase=location_phrase,
            geom_confidence=geom_conf, ward_id=ward_id, is_synthetic=True,
            photo_url=payload.photo_url, language=language, translated_text=translated_text,
            photo_severity_score=photo_severity_score, photo_severity_band=photo_severity_band,
            photo_checks=photo_checks,
        ),
        issue_id=issue_id, joined_existing_issue=joined_existing, category=category,
        category_confidence=category_conf, severity=severity_band,
        location_precision=_location_precision_from_breakdown(breakdown),
        priority_score=total, priority_breakdown=breakdown, matched_work=match_summary,
        signals=[
            SignalSummary(signal_id=r["id"], issue_id=r["issue_id"], match_id=r["match_id"],
                           rule_name=r["rule_name"], explanation=r["explanation"],
                           source_record_ids=r["source_record_ids"])
            for r in signal_rows
        ],
        is_synthetic=True,
    )
