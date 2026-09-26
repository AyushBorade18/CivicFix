"""Security boundary tests: authentication, role/scope authorization, report
ownership and the public API projection.

Runs against the isolated civicfix_test database. Tokens are real RS256 JWTs
signed by a keypair generated per test session and verified through the
production JWKS code path (a file:// JWKS), not a mocked verifier.
"""
import functools
import json
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.api.main import app
from app.users import assign_department, assign_ward, create_user, set_active

ISSUER = "https://issuer.test.civicfix"
AUDIENCE = "civicfix-api-test"
KID = "test-key-1"


@pytest.fixture(scope="session")
def signing_key(tmp_path_factory):
    """A throwaway keypair whose public JWKS is served over localhost HTTP,
    the same way a provider serves it (PyJWKClient refuses file:// URLs)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    directory = tmp_path_factory.mktemp("jwks")
    (directory / "jwks.json").write_text(json.dumps({"keys": [{**jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}))
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *args: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield key, f"http://127.0.0.1:{server.server_port}/jwks.json"
    server.shutdown()


@pytest.fixture(autouse=True)
def auth_env(monkeypatch, signing_key):
    monkeypatch.setenv("AUTH_JWKS_URL", signing_key[1])
    monkeypatch.setenv("AUTH_ISSUER", ISSUER)
    monkeypatch.setenv("AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("AUTH_ALGORITHMS", raising=False)


@pytest.fixture
def make_token(signing_key):
    def _make(sub, key=None, **overrides):
        now = int(time.time())
        claims = {"sub": sub, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300, **overrides}
        return jwt.encode(claims, key or signing_key[0], algorithm="RS256", headers={"kid": KID})
    return _make


@pytest.fixture
def client():
    return TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(db_conn):
    """Two wards, two issues, two citizens with one report each, and one of
    every staff role. Removed afterwards."""
    tag = uuid.uuid4().hex[:8]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM wards ORDER BY id LIMIT 2")
        ward_1, ward_2 = (r[0] for r in cur.fetchall())

    users = {
        name: create_user(db_conn, f"test|{name}|{tag}", role)
        for name, role in [
            ("alice", "citizen"), ("bob", "citizen"), ("ward_officer", "ward_officer"),
            ("dept_officer", "department_officer"), ("admin", "system_admin"), ("inactive", "citizen"),
        ]
    }
    assign_ward(db_conn, users["ward_officer"].external_auth_id, ward_1)
    # PMC Road Department owns pothole_road (and footpath), not drainage.
    assign_department(db_conn, users["dept_officer"].external_auth_id, "PMC Road Department")
    set_active(db_conn, users["inactive"].external_auth_id, False)

    breakdown = json.dumps({"total": 0.5, "exposure_detail": {"spatial_basis": "precise"}})
    with db_conn.cursor() as cur:
        issues = {}
        for name, category, ward in [("road_w1", "pothole_road", ward_1), ("drain_w2", "drainage_sewage", ward_2)]:
            cur.execute(
                "INSERT INTO issues (category, ward_id, status, report_count, first_reported, last_reported, "
                "priority_score, priority_breakdown, geom) VALUES (%s, %s, 'closed', 1, now(), now(), 0.5, "
                "%s::jsonb, ST_SetSRID(ST_MakePoint(73.856789, 18.520432), 4326)) RETURNING id",
                (category, ward, breakdown),
            )
            issues[name] = cur.fetchone()[0]
        reports = {}
        for name, issue, owner in [("alice", "road_w1", "alice"), ("bob", "drain_w2", "bob")]:
            cur.execute(
                "INSERT INTO reports (raw_text, reported_at, category, issue_id, reporter_user_id, is_synthetic) "
                "VALUES (%s, now(), (SELECT category FROM issues WHERE id = %s), %s, %s, false) RETURNING id",
                (f"private words from {name} {tag}", issues[issue], issues[issue], users[owner].id),
            )
            reports[name] = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO signals (issue_id, rule_name, explanation, source_record_ids) "
            "VALUES (%s, 'test_rule', 'internal explanation', '{}'::jsonb)",
            (issues["road_w1"],),
        )
    db_conn.commit()

    yield {"users": users, "issues": issues, "reports": reports, "ward_1": ward_1, "ward_2": ward_2, "tag": tag}

    user_ids = [u.id for u in users.values()]
    with db_conn.cursor() as cur:
        cur.execute("SELECT DISTINCT issue_id FROM reports WHERE reporter_user_id = ANY(%s)", (user_ids,))
        issue_ids = list({*issues.values(), *(r[0] for r in cur.fetchall() if r[0] is not None)})
        cur.execute("DELETE FROM feedback WHERE issue_id = ANY(%s)", (issue_ids,))
        cur.execute("DELETE FROM signals WHERE issue_id = ANY(%s)", (issue_ids,))
        cur.execute("DELETE FROM matches WHERE issue_id = ANY(%s)", (issue_ids,))
        cur.execute("DELETE FROM reports WHERE reporter_user_id = ANY(%s) OR issue_id = ANY(%s)",
                    (user_ids, issue_ids))
        cur.execute("DELETE FROM issues WHERE id = ANY(%s)", (issue_ids,))
        cur.execute("DELETE FROM users WHERE id = ANY(%s) OR external_auth_id LIKE %s", (user_ids, f"%|{tag}"))
    db_conn.commit()


@pytest.fixture
def as_user(world, make_token):
    return lambda name: auth(make_token(world["users"][name].external_auth_id))


# --- Authentication ------------------------------------------------------------

def test_missing_token_rejected(client, world):
    assert client.get("/api/me").status_code == 401


def test_garbage_token_rejected(client, world):
    assert client.get("/api/me", headers=auth("not.a.jwt")).status_code == 401


def test_token_signed_by_another_key_rejected(client, world, make_token):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(world["users"]["admin"].external_auth_id, key=other)
    assert client.get("/api/me", headers=auth(token)).status_code == 401


@pytest.mark.parametrize("claims", [
    {"exp": int(time.time()) - 10},
    {"iss": "https://someone-else.example"},
    {"aud": "another-api"},
])
def test_expired_or_foreign_token_rejected(client, world, make_token, claims):
    token = make_token(world["users"]["admin"].external_auth_id, **claims)
    assert client.get("/api/me", headers=auth(token)).status_code == 401


def test_unsigned_token_rejected(client, world):
    token = jwt.encode({"sub": world["users"]["admin"].external_auth_id, "iss": ISSUER, "aud": AUDIENCE,
                        "exp": int(time.time()) + 300}, None, algorithm="none")
    assert client.get("/api/me", headers=auth(token)).status_code == 401


def test_unknown_identity_rejected(client, world, make_token):
    assert client.get("/api/me", headers=auth(make_token("test|nobody|" + world["tag"]))).status_code == 403


def test_inactive_user_rejected(client, world, as_user):
    assert client.get("/api/me", headers=as_user("inactive")).status_code == 403


def test_valid_identity_returns_database_role_and_scope(client, world, as_user):
    body = client.get("/api/me", headers=as_user("ward_officer")).json()
    assert body["id"] == world["users"]["ward_officer"].id
    assert body["role"] == "ward_officer"
    assert body["ward_ids"] == [world["ward_1"]]


def test_role_claim_in_token_is_ignored(client, world, make_token):
    token = make_token(world["users"]["alice"].external_auth_id, role="system_admin", ward_ids=[world["ward_2"]])
    assert client.get("/api/me", headers=auth(token)).json()["role"] == "citizen"
    assert client.get(f"/api/issues/{world['issues']['drain_w2']}", headers=auth(token)).status_code == 403


def test_auth_not_configured_fails_closed(client, world, as_user, monkeypatch):
    headers = as_user("admin")
    monkeypatch.delenv("AUTH_JWKS_URL")
    assert client.get("/api/me", headers=headers).status_code == 503


def test_register_creates_citizen_and_ignores_requested_role(client, world, make_token, db_conn):
    sub = f"test|newcomer|{world['tag']}"
    token = make_token(sub, email="new@example.org", name="New Person")
    resp = client.post("/api/me/register", headers=auth(token), json={"role": "system_admin"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "citizen"
    assert resp.json()["email"] == "new@example.org"
    again = client.post("/api/me/register", headers=auth(token))
    assert again.json()["id"] == resp.json()["id"]


# --- Citizen authorization ---------------------------------------------------------

def test_citizen_sees_own_report(client, world, as_user):
    resp = client.get(f"/api/me/reports/{world['reports']['alice']}", headers=as_user("alice"))
    assert resp.status_code == 200
    assert resp.json()["issue_status"] == "closed"


def test_citizen_cannot_see_another_citizens_report(client, world, as_user):
    assert client.get(f"/api/me/reports/{world['reports']['bob']}", headers=as_user("alice")).status_code == 404


def test_my_reports_lists_only_own_reports_and_ignores_user_id_param(client, world, as_user):
    resp = client.get("/api/me/reports", params={"user_id": world["users"]["bob"].id}, headers=as_user("alice"))
    assert [r["report_id"] for r in resp.json()] == [world["reports"]["alice"]]


@pytest.mark.parametrize("method,path", [
    ("get", "/api/issues"),
    ("get", "/api/issues/{road}"),
    ("get", "/api/matches"),
    ("get", "/api/works"),
    ("get", "/api/map"),
    ("get", "/api/metrics"),
    ("post", "/api/issues/{road}/close"),
    ("post", "/api/issues/{road}/route"),
])
def test_citizen_blocked_from_internal_endpoints(client, world, as_user, method, path):
    url = path.format(road=world["issues"]["road_w1"])
    assert getattr(client, method)(url, headers=as_user("alice")).status_code == 403


def test_internal_endpoints_require_a_token(client, world):
    assert client.get(f"/api/issues/{world['issues']['road_w1']}").status_code == 401
    assert client.post(f"/api/issues/{world['issues']['road_w1']}/close").status_code == 401


def test_feedback_only_from_a_reporter_of_that_issue(client, world, as_user):
    road = world["issues"]["road_w1"]
    assert client.post(f"/api/issues/{road}/feedback", headers=as_user("bob"),
                       json={"resolved_confirmed": False}).status_code == 403
    resp = client.post(f"/api/issues/{road}/feedback", headers=as_user("alice"),
                       json={"resolved_confirmed": True})
    assert resp.status_code == 201
    assert resp.json()["feedback"]["is_synthetic"] is False


# --- Ward officer --------------------------------------------------------------------

def test_ward_officer_can_read_own_ward_intelligence(client, world, as_user):
    resp = client.get(f"/api/issues/{world['issues']['road_w1']}", headers=as_user("ward_officer"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority_breakdown"] is not None
    assert [s["rule_name"] for s in body["signals"]] == ["test_rule"]


def test_ward_officer_blocked_from_other_ward(client, world, as_user):
    drain = world["issues"]["drain_w2"]
    assert client.get(f"/api/issues/{drain}", headers=as_user("ward_officer")).status_code == 403
    assert client.post(f"/api/issues/{drain}/close", headers=as_user("ward_officer")).status_code == 403
    assert client.post(f"/api/issues/{drain}/route", headers=as_user("ward_officer")).status_code == 403


def test_ward_officer_issue_list_is_scoped_even_when_asking_for_another_ward(client, world, as_user):
    headers = as_user("ward_officer")
    listed = client.get("/api/issues", params={"limit": 200}, headers=headers).json()["items"]
    assert {i["ward_id"] for i in listed} == {world["ward_1"]}
    other = client.get("/api/issues", params={"ward_id": world["ward_2"]}, headers=headers).json()
    assert other["total"] == 0


def test_ward_officer_can_route_in_scope_issue(client, world, as_user):
    resp = client.post(f"/api/issues/{world['issues']['road_w1']}/route", headers=as_user("ward_officer"))
    assert resp.status_code == 200
    assert resp.json()["routed_agency"] == "PMC Road Department"


def test_system_admin_is_unrestricted(client, world, as_user):
    for issue in world["issues"].values():
        assert client.get(f"/api/issues/{issue}", headers=as_user("admin")).status_code == 200


# --- Department officer -----------------------------------------------------------

def test_department_officer_sees_own_department_categories_across_wards(client, world, as_user):
    headers = as_user("dept_officer")
    assert client.get(f"/api/issues/{world['issues']['road_w1']}", headers=headers).status_code == 200
    assert client.get(f"/api/issues/{world['issues']['drain_w2']}", headers=headers).status_code == 403
    listed = client.get("/api/issues", params={"limit": 200}, headers=headers).json()["items"]
    assert listed and {i["category"] for i in listed} <= {"pothole_road", "footpath"}


# --- Public API -----------------------------------------------------------------------

INTERNAL_FIELDS = {"priority_score", "priority_breakdown", "signals", "reports", "matches", "feedback",
                   "routed_agency", "routed_at", "raw_text", "reporter_user_id", "embedding"}


def test_public_issue_needs_no_token_and_exposes_nothing_internal(client, world):
    resp = client.get(f"/api/public/issues/{world['issues']['road_w1']}")
    assert resp.status_code == 200
    body = resp.json()
    assert not INTERNAL_FIELDS & body.keys()
    assert world["tag"] not in resp.text  # no report text anywhere in the payload
    assert "internal explanation" not in resp.text
    # coordinates rounded to ~100 m, labelled as approximate
    assert body["location"] == {"lat": 18.52, "lon": 73.857}
    assert body["location_precision"] == "approximate"


def test_public_list_and_map_expose_nothing_internal(client, world):
    listed = client.get("/api/public/issues", params={"limit": 200})
    mapped = client.get("/api/public/map")
    assert listed.status_code == mapped.status_code == 200
    for item in listed.json()["items"] + mapped.json()["issues"]:
        assert not INTERNAL_FIELDS & item.keys()
    assert "internal explanation" not in listed.text + mapped.text


def test_public_list_unknown_category_is_empty_not_an_error(client, world):
    resp = client.get("/api/public/issues", params={"category": "not_a_category"})
    assert resp.status_code == 200 and resp.json()["total"] == 0


# --- Ownership on submission ------------------------------------------------------

def test_report_submission_is_owned_by_the_token_holder_and_redacted(client, world, as_user, db_conn):
    marker = f"zzqx automated ownership test marker {world['tag']} aaa bbb ccc"
    resp = client.post("/api/reports", headers=as_user("alice"),
                       json={"raw_text": marker, "reporter_user_id": world["users"]["bob"].id})
    assert resp.status_code == 201
    body = resp.json()
    with db_conn.cursor() as cur:
        cur.execute("SELECT reporter_user_id, is_synthetic FROM reports WHERE id = %s", (body["report"]["id"],))
        assert cur.fetchone() == (world["users"]["alice"].id, False)
    # internal fields removed for a citizen
    assert body["priority_score"] is None and body["priority_breakdown"] is None
    assert body["signals"] == [] and body["matched_work"] is None
    assert body["severity"] is None and body["category_confidence"] is None
    mine = client.get("/api/me/reports", headers=as_user("alice")).json()
    assert body["report"]["id"] in [r["report_id"] for r in mine]
    theirs = client.get("/api/me/reports", headers=as_user("bob")).json()
    assert body["report"]["id"] not in [r["report_id"] for r in theirs]


def test_report_submission_requires_a_token(client, world):
    assert client.post("/api/reports", json={"raw_text": "anonymous"}).status_code == 401
