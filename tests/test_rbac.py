"""PMC hierarchy RBAC: ward officers scoped by ward office, zonal
commissioners by zone, system_admin-only account management, the audit log
and the role dashboard. Real RS256 tokens, isolated civicfix_test database."""
import csv
import uuid

import pytest

from app.ingest.wards import WARD_OFFICES_CSV
from app.users import assign_department, create_user
from tests.test_auth import auth, auth_env, client, make_token, signing_key  # noqa: F401


@pytest.fixture
def org(db_conn):
    """Zone Z with office A (wards w1, w2) and office B (ward w3); an open
    pothole issue with a real report in w1 and in w3; one user per role."""
    tag = uuid.uuid4().hex[:8]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id, ward_office_id FROM wards ORDER BY id LIMIT 3")
        original = cur.fetchall()
        w1, w2, w3 = (r[0] for r in original)
        cur.execute("INSERT INTO zones (name) VALUES (%s) RETURNING id", (f"Zone {tag}",))
        zone = cur.fetchone()[0]
        offices = {}
        for name, wards in [("A", [w1, w2]), ("B", [w3])]:
            cur.execute("INSERT INTO ward_offices (name, zone_id) VALUES (%s, %s) RETURNING id", (f"{name}-{tag}", zone))
            offices[name] = cur.fetchone()[0]
            cur.execute("UPDATE wards SET ward_office_id = %s WHERE id = ANY(%s)", (offices[name], wards))
        issues = {}
        for name, ward in [("w1", w1), ("w3", w3)]:
            cur.execute("INSERT INTO issues (category, ward_id, status, report_count, first_reported, last_reported, "
                        "priority_score) VALUES ('pothole_road', %s, 'open', 1, now(), now(), 0.5) RETURNING id", (ward,))
            issues[name] = cur.fetchone()[0]
            cur.execute("INSERT INTO reports (raw_text, reported_at, category, issue_id, is_synthetic) "
                        "VALUES ('pothole', now(), 'pothole_road', %s, false)", (issues[name],))
    db_conn.commit()

    users = {name: create_user(db_conn, f"test|{name}|{tag}", role) for name, role in [
        ("amc", "ward_officer"), ("zonal", "zonal_commissioner"), ("admin", "system_admin"),
        ("dept", "department_officer"), ("citizen", "citizen")]}
    assign_department(db_conn, users["dept"].external_auth_id, "PMC Road Department")
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO user_ward_offices VALUES (%s, %s)", (users["amc"].id, offices["A"]))
        cur.execute("INSERT INTO user_zones VALUES (%s, %s)", (users["zonal"].id, zone))
    db_conn.commit()

    yield {"users": users, "issues": issues, "offices": offices, "zone": zone, "wards": (w1, w2, w3), "tag": tag}

    ids = [u.id for u in users.values()]
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM audit_log WHERE actor_user_id = ANY(%s)", (ids,))
        cur.execute("DELETE FROM reports WHERE issue_id = ANY(%s)", (list(issues.values()),))
        cur.execute("DELETE FROM issues WHERE id = ANY(%s)", (list(issues.values()),))
        cur.execute("DELETE FROM users WHERE id = ANY(%s)", (ids,))
        for ward_id, office_id in original:
            cur.execute("UPDATE wards SET ward_office_id = %s WHERE id = %s", (office_id, ward_id))
        cur.execute("DELETE FROM ward_offices WHERE zone_id = %s", (zone,))
        cur.execute("DELETE FROM zones WHERE id = %s", (zone,))
    db_conn.commit()


@pytest.fixture
def as_(org, make_token):
    return lambda name: auth(make_token(org["users"][name].external_auth_id))


def test_ward_officer_scoped_to_their_ward_office(client, org, as_):
    assert client.get(f"/api/issues/{org['issues']['w1']}", headers=as_("amc")).status_code == 200
    assert client.get(f"/api/issues/{org['issues']['w3']}", headers=as_("amc")).status_code == 403
    me = client.get("/api/me", headers=as_("amc")).json()
    assert me["ward_office_ids"] == [org["offices"]["A"]]
    assert set(me["ward_ids"]) == set(org["wards"][:2])


def test_zonal_commissioner_sees_every_office_in_zone(client, org, as_):
    for issue in org["issues"].values():
        assert client.get(f"/api/issues/{issue}", headers=as_("zonal")).status_code == 200
    listed = {i["issue_id"] for i in client.get("/api/issues?limit=200", headers=as_("zonal")).json()["items"]}
    assert set(org["issues"].values()) <= listed


@pytest.mark.parametrize("who", ["amc", "zonal", "dept", "citizen"])
def test_only_system_admin_manages_accounts(client, org, as_, who):
    target = org["users"]["citizen"].id
    assert client.get("/api/admin/users", headers=as_(who)).status_code == 403
    assert client.patch(f"/api/admin/users/{target}", json={"role": "system_admin"},
                        headers=as_(who)).status_code == 403
    assert client.get("/api/admin/audit", headers=as_(who)).status_code == 403


def test_admin_promotes_and_scopes_user_with_audit(client, org, as_):
    uid = org["users"]["citizen"].id
    r = client.patch(f"/api/admin/users/{uid}", json={"role": "ward_officer"}, headers=as_("admin"))
    assert r.status_code == 200 and r.json()["role"] == "ward_officer"
    r = client.put(f"/api/admin/users/{uid}/scope", json={"ward_office_ids": [org["offices"]["B"]]},
                   headers=as_("admin"))
    assert r.status_code == 200 and r.json()["effective_ward_count"] == 1
    # Takes effect on the very next request - no token change needed.
    assert client.get(f"/api/issues/{org['issues']['w3']}", headers=as_("citizen")).status_code == 200

    log = client.get("/api/admin/audit?target_type=user", headers=as_("admin")).json()
    mine = [e for e in log if e["target_id"] == str(uid)]
    assert [e["action"] for e in mine] == ["user.scope", "user.update"]
    assert mine[1]["details"]["role"] == {"from": "citizen", "to": "ward_officer"}
    assert mine[0]["actor_user_id"] == org["users"]["admin"].id


def test_admin_cannot_lock_themselves_out(client, org, as_):
    uid = org["users"]["admin"].id
    for body in ({"role": "ward_officer"}, {"is_active": False}):
        assert client.patch(f"/api/admin/users/{uid}", json=body, headers=as_("admin")).status_code == 400


def test_bad_scope_rejected(client, org, as_):
    uid = org["users"]["amc"].id
    assert client.put(f"/api/admin/users/{uid}/scope", json={"zone_ids": [-1]}, headers=as_("admin")).status_code == 400
    assert client.put(f"/api/admin/users/{uid}/scope", json={"departments": ["Nope"]},
                      headers=as_("admin")).status_code == 400
    # A rejected change leaves the old scope in place.
    assert client.get(f"/api/issues/{org['issues']['w1']}", headers=as_("amc")).status_code == 200


def test_officer_actions_are_audited(client, org, as_):
    issue = org["issues"]["w1"]
    assert client.post(f"/api/issues/{issue}/close", headers=as_("amc")).status_code == 200
    log = client.get("/api/admin/audit?target_type=issue", headers=as_("admin")).json()
    entry = next(e for e in log if e["target_id"] == str(issue))
    assert entry["action"] == "issue.close" and entry["actor_user_id"] == org["users"]["amc"].id


def test_dashboard_is_role_scoped(client, org, as_):
    amc = client.get("/api/dashboard", headers=as_("amc")).json()
    assert {r["ward_id"] for r in amc["by_ward"]} == {org["wards"][0]}
    assert f"A-{org['tag']}" in amc["scope_label"]
    zonal = client.get("/api/dashboard", headers=as_("zonal")).json()
    assert {org["offices"]["A"], org["offices"]["B"]} <= {r["ward_office_id"] for r in zonal["by_ward"]}
    assert zonal["scope_label"] == f"Zone {org['tag']}"
    assert client.get("/api/dashboard", headers=as_("citizen")).status_code == 403


def test_ward_office_sheet_covers_every_prabhag_once():
    with open(WARD_OFFICES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert sorted(int(r["ward_id"]) for r in rows) == list(range(1, 59))
    office_zone = {}
    for r in rows:
        assert office_zone.setdefault(r["ward_office"], r["zone"]) == r["zone"], r
    assert len(office_zone) == 15 and len(set(office_zone.values())) == 5
