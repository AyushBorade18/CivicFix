"""Administrators' portal backend: PMC org structure, staff accounts and
their scope, the audit log, and the role-shaped dashboard summary.

Account management is system_admin only. Every change writes an audit row in
the same transaction. Roles are never taken from a token - only from here.
"""
from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row

from app.api.schemas import (AuditEntry, DashboardIssue, DashboardResponse, DashboardWardRow, OrgResponse,
                             OrgWard, OrgWardOffice, OrgZone, StaffUser, UserScopeRequest, UserUpdateRequest)
from app.auth import audit, issue_scope_sql, require_admin, require_staff
from app.db import get_db
from app.users import DEPARTMENTS, ROLES, CurrentUser, set_scope

router = APIRouter()


# --- Org structure -------------------------------------------------------------

@router.get("/api/admin/org", response_model=OrgResponse)
def org(db=Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Readable by all staff (to label scope); only admins can change who
    sits where. `verified=false` marks a drafted prabhag -> office mapping."""
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, name FROM zones ORDER BY name")
        zones = cur.fetchall()
        cur.execute("SELECT id, name, zone_id FROM ward_offices ORDER BY name")
        offices = cur.fetchall()
        cur.execute("SELECT id, name, ward_office_id, ward_office_verified AS verified FROM wards ORDER BY id")
        wards = cur.fetchall()

    def ward_list(office_id):
        return [OrgWard(id=w["id"], name=w["name"], verified=w["verified"])
                for w in wards if w["ward_office_id"] == office_id]

    return OrgResponse(
        zones=[OrgZone(id=z["id"], name=z["name"], ward_offices=[
            OrgWardOffice(id=o["id"], name=o["name"], wards=ward_list(o["id"]))
            for o in offices if o["zone_id"] == z["id"]]) for z in zones],
        unmapped_wards=ward_list(None),
        roles=list(ROLES),
        departments=list(DEPARTMENTS),
    )


# --- Staff accounts ------------------------------------------------------------

_USER_SQL = """
    SELECT u.id, u.external_auth_id, u.email, u.display_name, u.role, u.is_active,
      ARRAY(SELECT ward_id FROM user_wards WHERE user_id = u.id ORDER BY 1) AS ward_ids,
      ARRAY(SELECT ward_office_id FROM user_ward_offices WHERE user_id = u.id ORDER BY 1) AS ward_office_ids,
      ARRAY(SELECT zone_id FROM user_zones WHERE user_id = u.id ORDER BY 1) AS zone_ids,
      ARRAY(SELECT department FROM user_departments WHERE user_id = u.id ORDER BY 1) AS departments,
      (SELECT count(*) FROM (
         SELECT ward_id FROM user_wards WHERE user_id = u.id
         UNION SELECT w.id FROM wards w JOIN user_ward_offices uo ON uo.ward_office_id = w.ward_office_id
           WHERE uo.user_id = u.id
         UNION SELECT w.id FROM wards w JOIN ward_offices o ON o.id = w.ward_office_id
           JOIN user_zones uz ON uz.zone_id = o.zone_id WHERE uz.user_id = u.id) s) AS effective_ward_count
    FROM users u
"""


def _load_user(db, user_id: int) -> StaffUser:
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(_USER_SQL + " WHERE u.id = %s", (user_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"user {user_id} not found")
    return StaffUser(**row)


@router.get("/api/admin/users", response_model=list[StaffUser])
def list_users(role: Optional[str] = None, q: Optional[str] = None, db=Depends(get_db),
               user: CurrentUser = Depends(require_admin)):
    """Staff first, then citizens (who can be promoted after they register).
    `q` matches email, name or provider subject."""
    where, params = ["TRUE"], {}
    if role:
        where.append("u.role = %(role)s")
        params["role"] = role
    if q:
        where.append("(u.email ILIKE %(q)s OR u.display_name ILIKE %(q)s OR u.external_auth_id ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(_USER_SQL + f" WHERE {' AND '.join(where)} "
                    "ORDER BY (u.role = 'citizen'), u.role, u.display_name NULLS LAST, u.id LIMIT 200", params)
        return [StaffUser(**r) for r in cur.fetchall()]


@router.patch("/api/admin/users/{user_id}", response_model=StaffUser)
def update_user(user_id: int, payload: UserUpdateRequest, db=Depends(get_db),
                user: CurrentUser = Depends(require_admin)):
    before = _load_user(db, user_id)
    if payload.role is not None and payload.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"unknown role {payload.role!r}; expected one of {list(ROLES)}")
    # An admin can't lock themselves out; another admin has to do it.
    if user_id == user.id and (payload.role not in (None, "system_admin") or payload.is_active is False):
        raise HTTPException(status_code=400, detail="you cannot demote or deactivate your own account")
    changes = {k: v for k, v in payload.model_dump(exclude_none=True).items() if getattr(before, k) != v}
    if changes:
        with db.cursor() as cur:
            for col, value in changes.items():  # col is a model field name, never user input
                cur.execute(f"UPDATE users SET {col} = %s, updated_at = now() WHERE id = %s", (value, user_id))
        audit(db, user, "user.update", "user", user_id,
              {k: {"from": getattr(before, k), "to": v} for k, v in changes.items()})
        db.commit()
    return _load_user(db, user_id)


@router.put("/api/admin/users/{user_id}/scope", response_model=StaffUser)
def update_scope(user_id: int, payload: UserScopeRequest, db=Depends(get_db),
                 user: CurrentUser = Depends(require_admin)):
    """Replace the user's whole scope. Ward officers normally get a ward
    office, zonal commissioners a zone, department officers a department."""
    before = _load_user(db, user_id)
    scope_keys = ("ward_ids", "ward_office_ids", "zone_ids", "departments")
    if all(sorted(set(getattr(payload, k))) == sorted(getattr(before, k)) for k in scope_keys):
        return before  # nothing changed: no write, no audit row
    try:
        set_scope(db, user_id, payload.ward_ids, payload.ward_office_ids, payload.zone_ids, payload.departments)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except psycopg.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="unknown ward, ward office or zone id")
    audit(db, user, "user.scope", "user", user_id, {
        "from": before.model_dump(include={"ward_ids", "ward_office_ids", "zone_ids", "departments"}),
        "to": payload.model_dump(),
    })
    db.commit()
    return _load_user(db, user_id)


@router.get("/api/admin/audit", response_model=list[AuditEntry])
def audit_log(limit: int = Query(100, ge=1, le=500), target_type: Optional[str] = None,
              db=Depends(get_db), user: CurrentUser = Depends(require_admin)):
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT a.id, a.at, a.actor_user_id, coalesce(u.display_name, u.email) AS actor_name, a.action, "
            "a.target_type, a.target_id, a.details FROM audit_log a LEFT JOIN users u ON u.id = a.actor_user_id "
            "WHERE (%(t)s::text IS NULL OR a.target_type = %(t)s) ORDER BY a.at DESC, a.id DESC LIMIT %(n)s",
            {"t": target_type, "n": limit},
        )
        return [AuditEntry(**r) for r in cur.fetchall()]


# --- Role dashboard --------------------------------------------------------------

def _scope_label(db, user: CurrentUser) -> str:
    if user.role == "system_admin":
        return "All of PMC"
    if user.role == "department_officer":
        return ", ".join(sorted(user.departments)) or "No department assigned"
    with db.cursor() as cur:
        cur.execute("SELECT name FROM zones WHERE id = ANY(%s) ORDER BY name", (sorted(user.zone_ids),))
        parts = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT name || ' ward office' FROM ward_offices WHERE id = ANY(%s) ORDER BY name",
                    (sorted(user.ward_office_ids),))
        parts += [r[0] for r in cur.fetchall()]
    if not parts and user.ward_ids:
        parts.append(f"{len(user.ward_ids)} prabhag(s)")
    return ", ".join(parts) or "No wards assigned"


@router.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(db=Depends(get_db), user: CurrentUser = Depends(require_staff)):
    scope, params = issue_scope_sql(user, "i")
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT w.id AS ward_id, w.name AS ward_name, o.id AS ward_office_id, o.name AS ward_office, "
            "z.id AS zone_id, z.name AS zone, "
            "count(*) FILTER (WHERE i.status <> 'closed') AS open, "
            "count(*) FILTER (WHERE i.status = 'closed') AS closed, "
            "count(*) FILTER (WHERE i.status <> 'closed' AND i.routed_agency IS NULL) AS unrouted, "
            "round((avg(extract(epoch FROM now() - i.first_reported) / 86400) "
            "      FILTER (WHERE i.status <> 'closed'))::numeric, 1)::float AS avg_open_age_days "
            "FROM issues i LEFT JOIN wards w ON w.id = i.ward_id "
            "LEFT JOIN ward_offices o ON o.id = w.ward_office_id LEFT JOIN zones z ON z.id = o.zone_id "
            f"WHERE {scope} GROUP BY w.id, w.name, o.id, o.name, z.id, z.name ORDER BY z.name, o.name, w.id",
            params,
        )
        by_ward = [DashboardWardRow(**r) for r in cur.fetchall()]
        cur.execute(f"SELECT i.category::text AS category, count(*) AS n FROM issues i "
                    f"WHERE {scope} AND i.status <> 'closed' GROUP BY 1 ORDER BY 2 DESC", params)
        by_category = {r["category"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            "SELECT i.id AS issue_id, i.category::text AS category, i.ward_id, w.name AS ward_name, "
            "i.priority_score, i.report_count, i.first_reported, i.routed_agency "
            f"FROM issues i LEFT JOIN wards w ON w.id = i.ward_id WHERE {scope} AND i.status <> 'closed' "
            "ORDER BY i.priority_score DESC NULLS LAST, i.id LIMIT 10",
            params,
        )
        top = [DashboardIssue(**r) for r in cur.fetchall()]
    return DashboardResponse(role=user.role, scope_label=_scope_label(db, user), by_ward=by_ward,
                             by_category=by_category, top_open_issues=top)
