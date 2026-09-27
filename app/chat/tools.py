"""The assistant's data access. Every fact it states comes from one of these
queries - there is no other source. Scope uses the same helpers as the API
(issue_scope_sql, live_issue_sql), and wherever an API function already does
the job (issue_detail, create_report, route_issue_endpoint, submit_feedback)
the engine calls that function instead, so its checks and audit rows apply.

The only write here is answer_dispatch_check, and it writes an audit row.
"""
from datetime import datetime
from typing import Optional

from psycopg.rows import dict_row

from app.auth import audit, issue_scope_sql, live_issue_sql
from app.core.recurrence import RECURRENCE_RADIUS_M
from app.users import WARD_SCOPED_ROLES, CurrentUser

# Same cut-offs as the admin UI's P1/P2 bands (web/src/admin/components/ws.tsx).
HIGH_PRIORITY = 0.7
MED_PRIORITY = 0.4
DEADLINE_WINDOW_DAYS = 7

# Needs a human look: reopened after a resolution, citizen evidence waiting
# for review, or a public-work verification signal (every such signal is tied
# to a match - app/core/signals.py).
VERIFICATION_SQL = (
    "(i.status = 'reopened'"
    " OR EXISTS (SELECT 1 FROM evidence e WHERE e.issue_id = i.id AND e.review_status = 'pending_review')"
    " OR EXISTS (SELECT 1 FROM signals s WHERE s.issue_id = i.id AND s.match_id IS NOT NULL))"
)

_CONFIRMED_SQL = (
    "EXISTS (SELECT 1 FROM feedback f WHERE f.issue_id = i.id AND f.resolved_confirmed "
    "AND (i.closed_at IS NULL OR f.submitted_at >= i.closed_at)) AS reporter_confirmed"
)
_ISSUE_SQL = f"""
    SELECT i.id, i.category::text AS category, i.ward_id, w.name AS ward_name, i.status, i.report_count,
           i.first_reported, i.last_reported, i.closed_at, i.reverification_due_at, i.recurrence_count,
           i.priority_score, i.priority_breakdown, i.routed_agency, i.assigned_worker_id, i.held_as_spam,
           ST_Y(i.geom) AS lat, ST_X(i.geom) AS lon, {_CONFIRMED_SQL}
    FROM issues i LEFT JOIN wards w ON w.id = i.ward_id
"""


def band(score: Optional[float]) -> str:
    s = score or 0.0
    return "high" if s >= HIGH_PRIORITY else "med" if s >= MED_PRIORITY else "low"


def issue_row(db, issue_id: int) -> Optional[dict]:
    """A live issue (not hidden test data, not held as spam), or None."""
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(f"{_ISSUE_SQL} WHERE i.id = %s AND {live_issue_sql('i')}", (issue_id,))
        return cur.fetchone()


def status_key(row: dict) -> tuple[str, dict]:
    """Status from recorded fields only. Resolved is not verified: 'verified'
    needs a reporter's confirmation after the closure."""
    if row.get("held_as_spam"):
        return "st_under_review", {}
    if row["status"] == "reopened":
        return "st_reopened", {}
    if row["status"] == "closed":
        if row.get("reporter_confirmed"):
            return "st_verified", {}
        due = row.get("reverification_due_at")
        if due is not None and due > datetime.now(due.tzinfo):
            return "st_resolved_window", {"date": f"{due:%d %b %Y}"}
        return "st_resolved", {}
    if row.get("assigned_worker_id") is not None:
        return "st_assigned", {}
    if row.get("routed_agency"):
        return "st_routed", {"agency": row["routed_agency"]}
    return "st_reported", {}


def is_reporter(db, user: Optional[CurrentUser], issue_id: int) -> bool:
    if user is None:
        return False
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM reports WHERE issue_id = %s AND reporter_user_id = %s LIMIT 1", (issue_id, user.id))
        return cur.fetchone() is not None


def my_reports(db, user: CurrentUser, limit: int = 5) -> list[dict]:
    """The caller's own reports only - ownership from the token, never input."""
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT r.id AS report_id, r.reported_at, i.id, i.category::text AS category, i.status, "
            f"i.report_count, i.closed_at, i.reverification_due_at, i.routed_agency, i.assigned_worker_id, "
            f"i.held_as_spam, {_CONFIRMED_SQL} "
            f"FROM reports r JOIN issues i ON i.id = r.issue_id WHERE r.reporter_user_id = %s "
            f"ORDER BY r.reported_at DESC LIMIT %s",
            (user.id, limit),
        )
        return cur.fetchall()


def related_work(db, issue_id: int) -> Optional[dict]:
    """The issue's matched public work, how many of its reports came after
    the recorded completion, and the verification signals that cite it."""
    from app.api.main import MATCH_JOIN_SQL  # app.api.main imports this package's router

    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(f"{MATCH_JOIN_SQL} WHERE m.issue_id = %s ORDER BY m.combined_score DESC LIMIT 1", (issue_id,))
        match = cur.fetchone()
        if match is None:
            return None
        reports_after = 0
        if match["completed_on"] is not None:
            cur.execute("SELECT count(*) AS n FROM reports WHERE issue_id = %s AND reported_at::date > %s",
                        (issue_id, match["completed_on"]))
            reports_after = cur.fetchone()["n"]
        cur.execute("SELECT id, rule_name, explanation, source_record_ids FROM signals "
                    "WHERE issue_id = %s AND match_id IS NOT NULL ORDER BY id", (issue_id,))
        signals = cur.fetchall()
    return {**match, "reports_after": reports_after, "signals": signals}


def history(db, issue: dict) -> Optional[dict]:
    """Earlier same-category issues within the recurrence radius of this one.
    None when the issue has no mapped point to compare from."""
    if issue["lat"] is None:
        return None
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT i.id, i.status, i.recurrence_count FROM issues i "
            f"WHERE i.id <> %(id)s AND i.category::text = %(category)s AND i.geom IS NOT NULL "
            f"AND i.first_reported < %(first)s AND {live_issue_sql('i')} "
            f"AND ST_DWithin(i.geom::geography, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(r)s) "
            f"ORDER BY i.first_reported",
            {"id": issue["id"], "category": issue["category"], "first": issue["first_reported"],
             "lat": issue["lat"], "lon": issue["lon"], "r": RECURRENCE_RADIUS_M},
        )
        rows = cur.fetchall()
    return {
        "radius_m": RECURRENCE_RADIUS_M, "ids": [r["id"] for r in rows],
        "closed": sum(r["status"] == "closed" for r in rows),
        "reopened": sum(r["recurrence_count"] > 0 for r in rows),
    }


def preview(db, raw_text: str, latitude: Optional[float], longitude: Optional[float]) -> dict:
    """What submitting would do, without writing anything: the same analysis
    and the same matching rule create_report uses, plus the recurrence rule
    (app/core/recurrence.py) when no open issue matches."""
    from app.api.main import analyse_report, find_matching_issue

    a = analyse_report(db, raw_text, None, latitude, longitude)
    report = {
        "category": a["category"], "geom_confidence": a["geom_conf"], "ward_id": a["ward_id"],
        "lat": a["lat"], "lon": a["lon"], "reported_at": datetime.now().astimezone(), "embedding": a["embedding"],
    }
    match_id = find_matching_issue(db, report)
    recurrence_id = None
    if match_id is None and a["ward_id"] is not None:
        near = ""
        params = {"category": a["category"], "ward_id": a["ward_id"], "r": RECURRENCE_RADIUS_M}
        if a["lat"] is not None:
            near = ("AND (i.geom IS NULL OR ST_DWithin(i.geom::geography, "
                    "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(r)s))")
            params.update(lat=a["lat"], lon=a["lon"])
        with db.cursor() as cur:
            cur.execute(
                f"SELECT i.id FROM issues i WHERE i.status = 'closed' AND i.category::text = %(category)s "
                f"AND i.ward_id = %(ward_id)s AND {live_issue_sql('i')} {near} ORDER BY i.last_reported DESC LIMIT 1",
                params,
            )
            row = cur.fetchone()
        recurrence_id = row[0] if row else None
    return {"category": a["category"], "ward_id": a["ward_id"], "geom_conf": a["geom_conf"],
            "match_issue_id": match_id, "recurrence_issue_id": recurrence_id}


def ward_name(db, ward_id: Optional[int]) -> Optional[str]:
    if ward_id is None:
        return None
    with db.cursor() as cur:
        cur.execute("SELECT name FROM wards WHERE id = %s", (ward_id,))
        row = cur.fetchone()
    return row[0] if row else None


# --- Confirmations ------------------------------------------------------------

def pending_prompt(db, user: CurrentUser) -> Optional[dict]:
    """A question the workflow is actually waiting on this citizen for, or
    None. Asked only when a record says so - never on every visit."""
    with db.cursor(row_factory=dict_row) as cur:
        # Staff opened a before-dispatch check on one of this citizen's reports.
        cur.execute(
            "SELECT a.id AS verification_id, r.issue_id FROM alternative_verifications a "
            "JOIN reports r ON r.id = a.report_id JOIN issues i ON i.id = r.issue_id "
            "WHERE r.reporter_user_id = %s AND a.status = 'initiated' AND i.status <> 'closed' "
            "ORDER BY a.initiated_at DESC LIMIT 1",
            (user.id,),
        )
        row = cur.fetchone()
        if row:
            return {"kind": "dispatch", **row}
        # An issue they reported was closed, its reverification window is
        # open, and nobody has answered since the closure.
        cur.execute(
            "SELECT i.id AS issue_id, i.closed_at FROM issues i WHERE i.status = 'closed' "
            "AND (i.reverification_due_at IS NULL OR i.reverification_due_at > now()) "
            "AND EXISTS (SELECT 1 FROM reports r WHERE r.issue_id = i.id AND r.reporter_user_id = %s) "
            "AND NOT EXISTS (SELECT 1 FROM feedback f WHERE f.issue_id = i.id AND f.submitted_at >= i.closed_at) "
            "ORDER BY i.closed_at DESC LIMIT 1",
            (user.id,),
        )
        row = cur.fetchone()
    return {"kind": "closed", **row} if row else None


def answer_dispatch_check(db, user: CurrentUser, verification_id: int, still_present: bool) -> Optional[int]:
    """The reporter answers a staff-opened before-dispatch check. Only the
    reporter of that report, only while it is still open. Returns the issue
    id, or None when there is nothing this user may answer."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT a.status, r.issue_id FROM alternative_verifications a JOIN reports r ON r.id = a.report_id "
            "WHERE a.id = %s AND r.reporter_user_id = %s",
            (verification_id, user.id),
        )
        row = cur.fetchone()
        if row is None or row[0] != "initiated":
            return None
        status = "confirmed" if still_present else "not_confirmed"
        cur.execute(
            "UPDATE alternative_verifications SET status = %s, completed_by = %s, completed_at = now(), "
            "notes = concat_ws(' ', notes, 'Answered by the reporter in CivicFix Assistant.') WHERE id = %s",
            (status, user.id, verification_id),
        )
    audit(db, user, "alternative_verification.reporter_answer", "alternative_verification", verification_id,
          {"status": status, "issue_id": row[1]})
    db.commit()
    return row[1]


# --- Staff --------------------------------------------------------------------

def has_scope(user: CurrentUser) -> bool:
    if user.role == "system_admin":
        return True
    if user.role in WARD_SCOPED_ROLES:
        return bool(user.ward_ids)
    return bool(user.departments)


def admin_issues(db, user: CurrentUser, *, category: Optional[str] = None, min_priority: Optional[float] = None,
                 recurring: bool = False, verification: bool = False, limit: int = 5) -> tuple[int, list[dict]]:
    """Open issues in the caller's scope, highest priority first."""
    scope, params = issue_scope_sql(user, "i")
    where = [scope, "i.status <> 'closed'"]
    if category:
        where.append("i.category::text = %(category)s")
        params["category"] = category
    if min_priority is not None:
        where.append("i.priority_score >= %(min_priority)s")
        params["min_priority"] = min_priority
    if recurring:
        where.append("(i.recurrence_count > 0 OR i.status = 'reopened')")
    if verification:
        where.append(VERIFICATION_SQL)
    where_sql = " AND ".join(where)
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT count(*) AS n FROM issues i WHERE {where_sql}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT i.id, i.category::text AS category, i.ward_id, w.name AS ward_name, i.status, i.report_count, "
            f"i.priority_score, i.recurrence_count FROM issues i LEFT JOIN wards w ON w.id = i.ward_id "
            f"WHERE {where_sql} ORDER BY i.priority_score DESC NULLS LAST, i.id LIMIT %(limit)s",
            {**params, "limit": limit},
        )
        return total, cur.fetchall()


def briefing(db, user: CurrentUser) -> dict:
    scope, params = issue_scope_sql(user, "i")
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT count(*) FILTER (WHERE i.status <> 'closed') AS open, "
            f"count(*) FILTER (WHERE i.status <> 'closed' AND i.priority_score >= %(high)s) AS high, "
            f"count(*) FILTER (WHERE i.status <> 'closed' AND {VERIFICATION_SQL}) AS verification, "
            f"count(*) FILTER (WHERE i.status = 'closed' AND i.reverification_due_at BETWEEN now() "
            f"  AND now() + make_interval(days => %(window)s)) AS deadlines, "
            f"count(*) FILTER (WHERE i.status <> 'closed' AND i.routed_agency IS NULL) AS unrouted "
            f"FROM issues i WHERE {scope}",
            {**params, "high": HIGH_PRIORITY, "window": DEADLINE_WINDOW_DAYS},
        )
        counts = cur.fetchone()
    _, top = admin_issues(db, user, verification=True, limit=1)
    return {**counts, "top_verification": top[0] if top else None}


def deadlines(db, user: CurrentUser) -> dict:
    """The real deadlines on record. CivicFix has no SLA targets, so this
    never claims an SLA breach - only reverification windows and open age."""
    scope, params = issue_scope_sql(user, "i")
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT i.id, i.category::text AS category, w.name AS ward_name, i.reverification_due_at "
            f"FROM issues i LEFT JOIN wards w ON w.id = i.ward_id WHERE {scope} AND i.status = 'closed' "
            f"AND i.reverification_due_at BETWEEN now() AND now() + make_interval(days => %(window)s) "
            f"ORDER BY i.reverification_due_at LIMIT 5",
            {**params, "window": DEADLINE_WINDOW_DAYS},
        )
        windows = cur.fetchall()
        cur.execute(
            f"SELECT i.id, i.category::text AS category, w.name AS ward_name, i.priority_score, "
            f"(now()::date - i.first_reported::date) AS age_days "
            f"FROM issues i LEFT JOIN wards w ON w.id = i.ward_id WHERE {scope} AND i.status <> 'closed' "
            f"ORDER BY i.first_reported LIMIT 3",
            params,
        )
        oldest = cur.fetchall()
    return {"windows": windows, "oldest": oldest}


def work_links(db, user: CurrentUser, work_id: int) -> Optional[dict]:
    """A public work and the issues in the caller's scope matched to it."""
    scope, params = issue_scope_sql(user, "i")
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id AS work_id, work_name, category::text AS category, status, completed_on, agency, cost "
                    "FROM works WHERE id = %s", (work_id,))
        work = cur.fetchone()
        if work is None:
            return None
        cur.execute(
            f"SELECT i.id, i.category::text AS category, w.name AS ward_name, i.status, i.report_count, "
            f"i.priority_score, m.match_reason FROM matches m JOIN issues i ON i.id = m.issue_id "
            f"LEFT JOIN wards w ON w.id = i.ward_id WHERE m.work_id = %(work_id)s AND {scope} "
            f"ORDER BY i.priority_score DESC NULLS LAST",
            {**params, "work_id": work_id},
        )
        return {**work, "issues": cur.fetchall()}
