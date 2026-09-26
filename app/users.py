"""CivicFix accounts: who a verified identity is, and what it may see.

The identity provider only proves "this is subject X". Role, wards and
departments live here, in our database, and are never taken from a token
claim or a request body.

Admin CLI (operator with database access; the admin HTTP API comes later):
  python -m app.users show <external_auth_id>
  python -m app.users create <external_auth_id> [--role ROLE] [--email E] [--name N]
  python -m app.users set-role <external_auth_id> <role>
  python -m app.users activate|deactivate <external_auth_id>
  python -m app.users assign-ward <external_auth_id> <ward_id>
  python -m app.users assign-department <external_auth_id> "<department>"
"""
import argparse
from dataclasses import dataclass
from typing import Optional

from psycopg.rows import dict_row

from app.core.routing import AGENCY_MAP

# field_worker: captures resolution evidence for assigned issues only; not staff.
ROLES = ("citizen", "ward_officer", "department_officer", "system_admin", "field_worker")
STAFF_ROLES = ("ward_officer", "department_officer", "system_admin")
DEPARTMENTS = tuple(sorted(set(AGENCY_MAP.values())))


@dataclass(frozen=True)
class CurrentUser:
    id: int
    external_auth_id: str
    email: Optional[str]
    display_name: Optional[str]
    role: str
    is_active: bool
    ward_ids: frozenset[int]
    departments: frozenset[str]

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def department_categories(self) -> list[str]:
        """Categories whose issues this user's departments own, per the same
        fixed category -> department table that routing uses."""
        return sorted(c for c, dept in AGENCY_MAP.items() if dept in self.departments)

    def can_access_issue(self, ward_id: Optional[int], category: str) -> bool:
        if self.role == "system_admin":
            return True
        if self.role == "ward_officer":
            return ward_id is not None and ward_id in self.ward_ids
        if self.role == "department_officer":
            return category in self.department_categories
        return False


def get_user(conn, external_auth_id: str) -> Optional[CurrentUser]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, external_auth_id, email, display_name, role, is_active FROM users "
            "WHERE external_auth_id = %s",
            (external_auth_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("SELECT ward_id FROM user_wards WHERE user_id = %s", (row["id"],))
        wards = frozenset(r["ward_id"] for r in cur.fetchall())
        cur.execute("SELECT department FROM user_departments WHERE user_id = %s", (row["id"],))
        departments = frozenset(r["department"] for r in cur.fetchall())
    return CurrentUser(**row, ward_ids=wards, departments=departments)


def create_user(conn, external_auth_id: str, role: str = "citizen",
                email: Optional[str] = None, display_name: Optional[str] = None) -> CurrentUser:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {ROLES}")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (external_auth_id, role, email, display_name) VALUES (%s, %s, %s, %s)",
            (external_auth_id, role, email, display_name),
        )
    conn.commit()
    return get_user(conn, external_auth_id)


def _update(conn, external_auth_id: str, sql: str, params: tuple) -> CurrentUser:
    with conn.cursor() as cur:
        cur.execute(f"UPDATE users SET {sql}, updated_at = now() WHERE external_auth_id = %s",
                    (*params, external_auth_id))
        if cur.rowcount == 0:
            raise ValueError(f"no user with external_auth_id {external_auth_id!r}")
    conn.commit()
    return get_user(conn, external_auth_id)


def set_role(conn, external_auth_id: str, role: str) -> CurrentUser:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {ROLES}")
    return _update(conn, external_auth_id, "role = %s", (role,))


def set_active(conn, external_auth_id: str, active: bool) -> CurrentUser:
    return _update(conn, external_auth_id, "is_active = %s", (active,))


def assign_ward(conn, external_auth_id: str, ward_id: int) -> CurrentUser:
    user = _require(conn, external_auth_id)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO user_wards (user_id, ward_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user.id, ward_id))
    conn.commit()
    return get_user(conn, external_auth_id)


def assign_department(conn, external_auth_id: str, department: str) -> CurrentUser:
    if department not in DEPARTMENTS:
        raise ValueError(f"unknown department {department!r}; expected one of {DEPARTMENTS}")
    user = _require(conn, external_auth_id)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_departments (user_id, department) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user.id, department),
        )
    conn.commit()
    return get_user(conn, external_auth_id)


def _require(conn, external_auth_id: str) -> CurrentUser:
    user = get_user(conn, external_auth_id)
    if user is None:
        raise ValueError(f"no user with external_auth_id {external_auth_id!r}")
    return user


def main(argv=None) -> None:
    from app.db import get_connection

    parser = argparse.ArgumentParser(prog="python -m app.users")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("show", "activate", "deactivate"):
        sub.add_parser(name).add_argument("external_auth_id")
    create = sub.add_parser("create")
    create.add_argument("external_auth_id")
    create.add_argument("--role", default="citizen", choices=ROLES)
    create.add_argument("--email")
    create.add_argument("--name")
    role = sub.add_parser("set-role")
    role.add_argument("external_auth_id")
    role.add_argument("role", choices=ROLES)
    ward = sub.add_parser("assign-ward")
    ward.add_argument("external_auth_id")
    ward.add_argument("ward_id", type=int)
    dept = sub.add_parser("assign-department")
    dept.add_argument("external_auth_id")
    dept.add_argument("department", choices=DEPARTMENTS)
    args = parser.parse_args(argv)

    conn = get_connection()
    try:
        if args.command == "show":
            user = _require(conn, args.external_auth_id)
        elif args.command == "create":
            user = create_user(conn, args.external_auth_id, args.role, args.email, args.name)
        elif args.command == "set-role":
            user = set_role(conn, args.external_auth_id, args.role)
        elif args.command in ("activate", "deactivate"):
            user = set_active(conn, args.external_auth_id, args.command == "activate")
        elif args.command == "assign-ward":
            user = assign_ward(conn, args.external_auth_id, args.ward_id)
        else:
            user = assign_department(conn, args.external_auth_id, args.department)
        print(user)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
