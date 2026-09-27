"""Location-verified evidence: an in-app camera photo submitted together with
the device's own location reading, its accuracy, the device capture time,
and the server's receipt time.

This is a verification signal for human review - never proof that anyone
was on site or that a complaint is true, and never a guilt signal. A report
without a photo is "pending" or "not provided", never false; staff can
confirm it through an alternative channel instead.

Citizens capture the "before" photo for their own report; field workers
capture the "after" photo for an issue assigned to them; staff review both.
Photos live in a private directory and are served only through an
authorized endpoint.
"""
import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import httpx
import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from psycopg.rows import dict_row

from app.api.schemas import (
    AlternativeVerification,
    AlternativeVerificationCompleteRequest,
    AlternativeVerificationCreateRequest,
    EvidenceItem,
    EvidenceUrlResponse,
    EvidenceReviewRequest,
    FieldWorker,
    GeoPoint,
    IssueAssignRequest,
    IssueAssignResponse,
)
from app.auth import audit, ensure_issue_access, get_current_user, issue_scope_sql, require_staff
from app.db import get_db
from app.users import CurrentUser

# Policy, not architecture: set per deployment. Each window is stamped on the
# row when it opens, so changing a value never moves a window already open.
EVIDENCE_SUBMISSION_WINDOW_DAYS = int(os.environ.get("EVIDENCE_SUBMISSION_WINDOW_DAYS", "7"))
REVERIFICATION_WINDOW_DAYS = int(os.environ.get("REVERIFICATION_WINDOW_DAYS", "7"))

EVIDENCE_DIR = Path("data/evidence")  # deliberately not mounted as static files
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024

# Photo storage. With SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY set, photos go
# to a PRIVATE Supabase Storage bucket (EVIDENCE_BUCKET, default
# "complaint-images"), keyed issues/<issue_id>/<uuid>.<ext>. The service key
# stays on this server; a browser gets a photo only after evidence_url /
# evidence_file check its access - as a short-lived signed URL or the bytes.
# Unset (local dev, tests): EVIDENCE_DIR on disk.
SIGNED_URL_SECONDS = 300


def _bucket() -> Optional[tuple[str, dict]]:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    bucket = os.environ.get("EVIDENCE_BUCKET", "complaint-images")
    return f"{url.rstrip('/')}/storage/v1/object/{bucket}", {"Authorization": f"Bearer {key}", "apikey": key}


def _store(file_key: str, body: bytes, mime_type: str) -> None:
    bucket = _bucket()
    if bucket is None:
        path = EVIDENCE_DIR / file_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return
    base, headers = bucket
    resp = httpx.post(f"{base}/{file_key}", headers={**headers, "Content-Type": mime_type, "x-upsert": "false"},
                      content=body, timeout=30)
    resp.raise_for_status()


def _load(file_key: str) -> bytes:
    bucket = _bucket()
    if bucket is None:
        return (EVIDENCE_DIR / file_key).read_bytes()
    base, headers = bucket
    resp = httpx.get(f"{base}/{file_key}", headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.content


def _signed_url(file_key: str) -> Optional[str]:
    """A URL that serves this one object for SIGNED_URL_SECONDS, or None when
    photos are on local disk (then only evidence_file can serve them)."""
    bucket = _bucket()
    if bucket is None:
        return None
    base, headers = bucket
    sign_base = base.replace("/storage/v1/object/", "/storage/v1/object/sign/", 1)
    resp = httpx.post(f"{sign_base}/{file_key}", headers=headers, json={"expiresIn": SIGNED_URL_SECONDS}, timeout=10)
    resp.raise_for_status()
    storage_root = base.split("/storage/v1/", 1)[0] + "/storage/v1"
    return storage_root + resp.json()["signedURL"]


def _discard(file_key: str) -> None:
    """Best effort: an orphaned photo with no row is harmless, a lost row isn't."""
    bucket = _bucket()
    try:
        if bucket is None:
            (EVIDENCE_DIR / file_key).unlink(missing_ok=True)
        else:
            httpx.delete(f"{bucket[0]}/{file_key}", headers=bucket[1], timeout=10)
    except (OSError, httpx.HTTPError):
        pass

router = APIRouter()


def location_precision_from_breakdown(breakdown: Optional[dict]) -> str:
    if not breakdown:
        return "unknown"
    basis = (breakdown.get("exposure_detail") or {}).get("spatial_basis")
    if basis == "precise":
        return "precise"
    if basis == "ward":
        return "ward_level"
    return "unknown"


def _sniff_image(body: bytes) -> Optional[tuple[str, str]]:
    """Type from the bytes themselves: the Content-Type header is whatever
    the client says it is."""
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def evidence_due_sql(alias: str = "r") -> str:
    # Reports from before migration 002 have no stamped window; derive one.
    return (f"COALESCE({alias}.evidence_due_at, "
            f"{alias}.reported_at + make_interval(days => {int(EVIDENCE_SUBMISSION_WINDOW_DAYS)}))")


def evidence_status_sql(alias: str = "r") -> str:
    """Per-report evidence state. A report with no photo is pending while its
    window is open and "not_provided" after - never "false"."""
    return f"""CASE
        WHEN EXISTS (SELECT 1 FROM evidence e WHERE e.report_id = {alias}.id
                     AND e.evidence_type = 'initial_report') THEN 'submitted'
        WHEN EXISTS (SELECT 1 FROM alternative_verifications a WHERE a.report_id = {alias}.id
                     AND a.status = 'confirmed') THEN 'alternative_confirmed'
        WHEN EXISTS (SELECT 1 FROM alternative_verifications a WHERE a.report_id = {alias}.id
                     AND a.status = 'initiated') THEN 'alternative_in_progress'
        WHEN now() <= {evidence_due_sql(alias)} THEN 'pending'
        ELSE 'not_provided'
    END"""


_EVIDENCE_SELECT = """
    SELECT e.id, e.issue_id, e.report_id, e.submitted_by, e.actor_type, e.evidence_type, e.capture_method,
           e.mime_type, e.byte_size, e.sha256, ST_Y(e.geom) AS lat, ST_X(e.geom) AS lon, e.accuracy_m,
           e.captured_at, e.location_captured_at, e.submitted_at, e.distance_from_issue_m,
           e.review_status, e.reviewed_by, e.reviewed_at, e.review_note, i.priority_breakdown
    FROM evidence e JOIN issues i ON i.id = e.issue_id
"""


def _item(r: dict, citizen_view: bool) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=r["id"], issue_id=r["issue_id"], report_id=r["report_id"], submitted_by=r["submitted_by"],
        actor_type=r["actor_type"], evidence_type=r["evidence_type"], capture_method=r["capture_method"],
        file_url=f"/api/evidence/{r['id']}/file", mime_type=r["mime_type"], byte_size=r["byte_size"],
        sha256=r["sha256"], location=GeoPoint(lat=r["lat"], lon=r["lon"]), accuracy_m=r["accuracy_m"],
        captured_at=r["captured_at"], location_captured_at=r["location_captured_at"],
        submitted_at=r["submitted_at"], distance_from_issue_m=r["distance_from_issue_m"],
        issue_location_precision=location_precision_from_breakdown(r["priority_breakdown"]),
        review_status=r["review_status"],
        reviewed_by=None if citizen_view else r["reviewed_by"],
        reviewed_at=r["reviewed_at"],
        review_note=None if citizen_view else r["review_note"],
    )


def evidence_items(db, issue_id: int, only_submitted_by: Optional[int] = None,
                   citizen_view: bool = False) -> list[EvidenceItem]:
    sql, params = f"{_EVIDENCE_SELECT} WHERE e.issue_id = %s", [issue_id]
    if only_submitted_by is not None:
        sql += " AND e.submitted_by = %s"
        params.append(only_submitted_by)
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(sql + " ORDER BY e.submitted_at, e.id", params)
        return [_item(r, citizen_view) for r in cur.fetchall()]


def _one_item(db, evidence_id: int, citizen_view: bool = False) -> EvidenceItem:
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(f"{_EVIDENCE_SELECT} WHERE e.id = %s", (evidence_id,))
        return _item(cur.fetchone(), citizen_view)


def _evidence_scope(user: CurrentUser, db, issue_id: int) -> Optional[int]:
    """None if the caller may see every capture on this issue, else the only
    submitter whose captures they may see (a citizen: themselves). Raises if
    the issue is out of reach. Citizens get 404, not 403, so they can't
    probe which issues exist."""
    if user.is_staff:
        ensure_issue_access(user, db, issue_id)
        return None
    with db.cursor() as cur:
        cur.execute("SELECT assigned_worker_id FROM issues WHERE id = %s", (issue_id,))
        row = cur.fetchone()
        if row is not None and user.role == "citizen":
            cur.execute("SELECT 1 FROM reports WHERE issue_id = %s AND reporter_user_id = %s LIMIT 1",
                        (issue_id, user.id))
            if cur.fetchone() is not None:
                return user.id
    if row is None or user.role != "field_worker":
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
    if row[0] != user.id:
        raise HTTPException(status_code=403, detail=f"issue {issue_id} is not assigned to you")
    return None  # an assigned worker needs the citizen's before photo


def alternative_verifications_for_issue(db, issue_id: int) -> list[AlternativeVerification]:
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT a.id, a.report_id, a.channel, a.status, a.initiated_by, a.initiated_at, a.completed_by, "
            "a.completed_at, a.notes FROM alternative_verifications a JOIN reports r ON r.id = a.report_id "
            "WHERE r.issue_id = %s ORDER BY a.initiated_at, a.id",
            (issue_id,),
        )
        return [AlternativeVerification(**r) for r in cur.fetchall()]


# --- Capture -------------------------------------------------------------------

@router.post("/api/issues/{issue_id}/evidence", response_model=EvidenceItem, status_code=201)
def submit_evidence(
    issue_id: int,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    client_submission_id: uuid.UUID = Form(...),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    accuracy_m: float = Form(..., ge=0, le=100_000),
    captured_at: Optional[datetime] = Form(None),
    location_captured_at: Optional[datetime] = Form(None),
    report_id: Optional[int] = Form(None),
    # 'upload': a file picked from disk; its location is the uploader's
    # device at upload time. Defaults to 'camera' for packages queued offline
    # by the old live-capture screen.
    capture_method: Literal["camera", "upload"] = Form("camera"),
    db=Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """One capture package: photo + device location + accuracy + device
    clock, stamped with the server clock on arrival. Citizens attach an
    initial photo to their own report while its evidence window is open;
    an assigned field worker attaches the resolution photo. Retrying with
    the same client_submission_id returns the first row (200), so a
    dropped connection can't create a duplicate."""
    with db.cursor() as cur:
        cur.execute("SELECT id, submitted_by FROM evidence WHERE client_submission_id = %s",
                    (str(client_submission_id),))
        existing = cur.fetchone()
    if existing is not None:
        if existing[1] != user.id:
            raise HTTPException(status_code=409, detail="client_submission_id already used")
        response.status_code = 200
        return _one_item(db, existing[0], citizen_view=not user.is_staff)

    # The reporter of a complaint attaches its photo. That is usually a
    # citizen, but staff may file a complaint from their own account too;
    # staff still can't attach photos to anyone else's report.
    if user.role not in ("citizen", "field_worker") and report_id is not None:
        with db.cursor() as cur:
            cur.execute("SELECT 1 FROM reports WHERE id = %s AND reporter_user_id = %s", (report_id, user.id))
            files_as_reporter = cur.fetchone() is not None
    else:
        files_as_reporter = user.role == "citizen"

    if files_as_reporter:
        if report_id is None:
            raise HTTPException(status_code=400, detail="report_id is required for citizen evidence")
        with db.cursor() as cur:
            cur.execute(
                f"SELECT issue_id, {evidence_due_sql()} AS due, now() > {evidence_due_sql()} AS expired "
                "FROM reports r WHERE r.id = %s AND r.reporter_user_id = %s",
                (report_id, user.id),
            )
            row = cur.fetchone()
            if row is None or row[0] != issue_id:
                raise HTTPException(status_code=404, detail=f"report {report_id} not found on issue {issue_id}")
            if row[2]:
                raise HTTPException(status_code=403,
                                    detail=f"the evidence window for this report closed on {row[1]:%d %b %Y}")
            cur.execute("SELECT 1 FROM evidence WHERE report_id = %s AND evidence_type = 'initial_report'",
                        (report_id,))
            if cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="a photo was already submitted for this report")
        actor_type, evidence_type = "citizen", "initial_report"
    elif user.role == "field_worker":
        if report_id is not None:
            raise HTTPException(status_code=400, detail="resolution evidence belongs to the issue, not a report")
        with db.cursor() as cur:
            cur.execute("SELECT status, assigned_worker_id FROM issues WHERE id = %s", (issue_id,))
            row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
        if row[1] != user.id:
            raise HTTPException(status_code=403, detail=f"issue {issue_id} is not assigned to you")
        if row[0] == "closed":
            raise HTTPException(status_code=409, detail=f"issue {issue_id} is already closed")
        actor_type, evidence_type = "worker", "resolution"
    else:
        raise HTTPException(status_code=403,
                            detail="evidence is captured by the reporting citizen or the assigned field worker")

    body = file.file.read(MAX_EVIDENCE_BYTES + 1)
    if len(body) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=400, detail=f"photo exceeds {MAX_EVIDENCE_BYTES // (1024 * 1024)}MB limit")
    sniffed = _sniff_image(body)
    if sniffed is None:
        raise HTTPException(status_code=400, detail="file is not a JPEG, PNG or WebP image")
    mime_type, ext = sniffed

    file_key = f"issues/{issue_id}/{uuid.uuid4().hex}{ext}"
    try:
        _store(file_key, body, mime_type)
    except (OSError, httpx.HTTPError):
        # Retryable: the device keeps the package and sends it again.
        raise HTTPException(status_code=503, detail="photo storage is unavailable - please try again")
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence (issue_id, report_id, submitted_by, actor_type, evidence_type, capture_method, file_key,
                                      mime_type, byte_size, sha256, geom, accuracy_m, captured_at,
                                      location_captured_at, distance_from_issue_m, client_submission_id, user_agent)
                SELECT i.id, %(report_id)s, %(user_id)s, %(actor)s, %(etype)s, %(method)s, %(key)s, %(mime)s, %(size)s,
                       %(sha)s, p.pt, %(acc)s, %(cap)s, %(loc_cap)s,
                       ST_Distance(p.pt::geography, i.geom::geography), %(sid)s, %(ua)s
                FROM issues i, (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS pt) p
                WHERE i.id = %(issue_id)s
                RETURNING id
                """,
                {
                    "issue_id": issue_id, "report_id": report_id, "user_id": user.id, "actor": actor_type,
                    "etype": evidence_type, "method": capture_method, "key": file_key, "mime": mime_type, "size": len(body),
                    "sha": hashlib.sha256(body).hexdigest(), "lat": latitude, "lon": longitude,
                    "acc": accuracy_m, "cap": captured_at, "loc_cap": location_captured_at,
                    "sid": str(client_submission_id), "ua": (request.headers.get("user-agent") or "")[:300],
                },
            )
            evidence_id = cur.fetchone()[0]
        db.commit()
    except psycopg.errors.UniqueViolation:
        # Lost a race with a concurrent retry or a second capture.
        db.rollback()
        _discard(file_key)
        raise HTTPException(status_code=409, detail="this capture or report already has evidence")
    except Exception:
        db.rollback()
        _discard(file_key)
        raise
    return _one_item(db, evidence_id, citizen_view=not user.is_staff)


# --- Read -------------------------------------------------------------------------

@router.get("/api/issues/{issue_id}/evidence", response_model=list[EvidenceItem])
def list_evidence(issue_id: int, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    only = _evidence_scope(user, db, issue_id)
    return evidence_items(db, issue_id, only_submitted_by=only, citizen_view=not user.is_staff)


@router.get("/api/evidence", response_model=list[EvidenceItem])
def evidence_queue(review_status: Optional[str] = Query(None, pattern="^(pending_review|verified|review_required)$"),
                   db=Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Every capture in the caller's scope, newest first - the verification workspace queue."""
    scope_sql, params = issue_scope_sql(user, alias="i")
    sql = f"{_EVIDENCE_SELECT} WHERE {scope_sql}"
    if review_status is not None:
        sql += " AND e.review_status = %(review_status)s"
        params["review_status"] = review_status
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(sql + " ORDER BY e.submitted_at DESC, e.id DESC", params)
        return [_item(r, citizen_view=False) for r in cur.fetchall()]


def _authorized_file(db, user: CurrentUser, evidence_id: int) -> tuple[str, str]:
    """(file_key, mime_type) if this user may see this photo, else 404/403."""
    with db.cursor() as cur:
        cur.execute("SELECT issue_id, submitted_by, file_key, mime_type FROM evidence WHERE id = %s", (evidence_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence {evidence_id} not found")
    issue_id, submitted_by, file_key, mime_type = row
    only = _evidence_scope(user, db, issue_id)
    if only is not None and only != submitted_by:
        raise HTTPException(status_code=404, detail=f"evidence {evidence_id} not found")
    return file_key, mime_type


@router.get("/api/evidence/{evidence_id}/url", response_model=EvidenceUrlResponse)
def evidence_url(evidence_id: int, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Same access rule as evidence_file. With a Storage bucket, returns a
    signed URL valid for SIGNED_URL_SECONDS; with local storage, url is null
    and the client fetches evidence_file with its token instead."""
    file_key, _ = _authorized_file(db, user, evidence_id)
    try:
        url = _signed_url(file_key)
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(status_code=502, detail=f"couldn't sign a URL for evidence {evidence_id}")
    return EvidenceUrlResponse(url=url, expires_in=SIGNED_URL_SECONDS if url else None)


@router.get("/api/evidence/{evidence_id}/file")
def evidence_file(evidence_id: int, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    file_key, mime_type = _authorized_file(db, user, evidence_id)
    try:
        body = _load(file_key)
    except (OSError, httpx.HTTPError):
        raise HTTPException(status_code=502, detail=f"photo for evidence {evidence_id} couldn't be retrieved")
    return Response(
        content=body, media_type=mime_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


# --- Staff actions ------------------------------------------------------------------

@router.post("/api/evidence/{evidence_id}/review", response_model=EvidenceItem)
def review_evidence(evidence_id: int, payload: EvidenceReviewRequest, db=Depends(get_db),
                    user: CurrentUser = Depends(require_staff)):
    """A human decision recorded against the signal - never automatic."""
    with db.cursor() as cur:
        cur.execute("SELECT issue_id FROM evidence WHERE id = %s", (evidence_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence {evidence_id} not found")
    ensure_issue_access(user, db, row[0])
    with db.cursor() as cur:
        cur.execute(
            "UPDATE evidence SET review_status = %s, review_note = %s, reviewed_by = %s, reviewed_at = now() "
            "WHERE id = %s",
            (payload.review_status, payload.note, user.id, evidence_id),
        )
    db.commit()
    return _one_item(db, evidence_id)


@router.get("/api/field-workers", response_model=list[FieldWorker])
def list_field_workers(db=Depends(get_db), user: CurrentUser = Depends(require_staff)):
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, display_name FROM users WHERE role = 'field_worker' AND is_active ORDER BY id")
        return [FieldWorker(**r) for r in cur.fetchall()]


@router.post("/api/issues/{issue_id}/assign", response_model=IssueAssignResponse)
def assign_issue(issue_id: int, payload: IssueAssignRequest, db=Depends(get_db),
                 user: CurrentUser = Depends(require_staff)):
    ensure_issue_access(user, db, issue_id)
    with db.cursor() as cur:
        cur.execute("SELECT role, is_active FROM users WHERE id = %s", (payload.worker_user_id,))
        worker = cur.fetchone()
        if worker is None or worker[0] != "field_worker" or not worker[1]:
            raise HTTPException(status_code=400, detail="assignee must be an active field worker")
        cur.execute(
            "UPDATE issues SET assigned_worker_id = %s, assigned_at = now() WHERE id = %s RETURNING assigned_at",
            (payload.worker_user_id, issue_id),
        )
        assigned_at = cur.fetchone()[0]
    audit(db, user, "issue.assign_worker", "issue", issue_id, {"worker_user_id": payload.worker_user_id})
    db.commit()
    return IssueAssignResponse(issue_id=issue_id, assigned_worker_id=payload.worker_user_id, assigned_at=assigned_at)


_ALT_COLUMNS = "id, report_id, channel, status, initiated_by, initiated_at, completed_by, completed_at, notes"


@router.post("/api/reports/{report_id}/alternative-verifications", response_model=AlternativeVerification,
             status_code=201)
def start_alternative_verification(report_id: int, payload: AlternativeVerificationCreateRequest,
                                   db=Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """The no-photo path: staff confirm the report through another channel
    (a call, WhatsApp, a site visit). Recording only - no channel is
    integrated yet."""
    with db.cursor() as cur:
        cur.execute("SELECT issue_id FROM reports WHERE id = %s", (report_id,))
        row = cur.fetchone()
    if row is None or row[0] is None:
        raise HTTPException(status_code=404, detail=f"report {report_id} not found")
    ensure_issue_access(user, db, row[0])
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"INSERT INTO alternative_verifications (report_id, channel, initiated_by, notes) "
            f"VALUES (%s, %s, %s, %s) RETURNING {_ALT_COLUMNS}",
            (report_id, payload.channel, user.id, payload.notes),
        )
        result = AlternativeVerification(**cur.fetchone())
    db.commit()
    return result


@router.post("/api/alternative-verifications/{verification_id}/complete", response_model=AlternativeVerification)
def complete_alternative_verification(verification_id: int, payload: AlternativeVerificationCompleteRequest,
                                      db=Depends(get_db), user: CurrentUser = Depends(require_staff)):
    with db.cursor() as cur:
        cur.execute(
            "SELECT a.status, r.issue_id FROM alternative_verifications a JOIN reports r ON r.id = a.report_id "
            "WHERE a.id = %s",
            (verification_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"verification {verification_id} not found")
    ensure_issue_access(user, db, row[1])
    if row[0] != "initiated":
        raise HTTPException(status_code=409, detail=f"verification {verification_id} is already {row[0]}")
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"UPDATE alternative_verifications SET status = %s, completed_by = %s, completed_at = now(), "
            f"notes = COALESCE(%s, notes) WHERE id = %s RETURNING {_ALT_COLUMNS}",
            (payload.status, user.id, payload.notes, verification_id),
        )
        result = AlternativeVerification(**cur.fetchone())
    db.commit()
    return result
