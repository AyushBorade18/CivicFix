"""Location-verified evidence: capture package storage, ownership,
idempotent retries, evidence/reverification windows, worker resolution
evidence, staff review and the no-photo alternative path.

Reuses test_auth's real-JWT fixtures (tokens verified through the
production JWKS path), against the isolated civicfix_test database.
"""
import json
import os
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.users import create_user
from tests.test_auth import auth, auth_env, client, make_token, signing_key, world  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 256  # magic bytes are all the server sniffs
ISSUE_LAT, ISSUE_LON = 18.520432, 73.856789  # world's issue location


@pytest.fixture
def ev(world, db_conn, make_token, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.evidence.EVIDENCE_DIR", tmp_path)  # never write into data/evidence
    monkeypatch.delenv("SUPABASE_URL", raising=False)  # local storage unless a test opts in
    worker = create_user(db_conn, f"test|worker|{world['tag']}", "field_worker")
    other_worker = create_user(db_conn, f"test|worker2|{world['tag']}", "field_worker")
    db_conn.commit()
    users = {**world["users"], "worker": worker, "other_worker": other_worker}
    yield {**world, "users": users, "as": lambda name: auth(make_token(users[name].external_auth_id))}
    issue_ids = list(world["issues"].values())
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM evidence WHERE issue_id = ANY(%s)", (issue_ids,))
        cur.execute("DELETE FROM alternative_verifications WHERE report_id = ANY(%s)",
                    (list(world["reports"].values()),))
        cur.execute("UPDATE issues SET assigned_worker_id = NULL WHERE id = ANY(%s)", (issue_ids,))
    db_conn.commit()


def submit(client, headers, issue_id, report_id=None, lat=ISSUE_LAT + 0.001, lon=ISSUE_LON,
           submission_id=None, body=JPEG, accuracy=8.5, capture_method=None):
    data = {
        "client_submission_id": submission_id or str(uuid.uuid4()),
        "latitude": str(lat), "longitude": str(lon), "accuracy_m": str(accuracy),
        "captured_at": "2026-09-26T14:32:00+05:30", "location_captured_at": "2026-09-26T14:31:58+05:30",
    }
    if report_id is not None:
        data["report_id"] = str(report_id)
    if capture_method is not None:
        data["capture_method"] = capture_method
    if lat is None:
        del data["latitude"]
    return client.post(f"/api/issues/{issue_id}/evidence", headers=headers, data=data,
                       files={"file": ("capture.jpg", body, "image/jpeg")})


# --- Citizen capture package -------------------------------------------------

def test_citizen_evidence_stores_the_whole_capture_package(client, ev):
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"])
    assert resp.status_code == 201, resp.text
    e = resp.json()
    assert e["actor_type"] == "citizen" and e["evidence_type"] == "initial_report"
    assert e["capture_method"] == "camera" and e["report_id"] == ev["reports"]["alice"]
    assert e["location"] == {"lat": pytest.approx(ISSUE_LAT + 0.001), "lon": pytest.approx(ISSUE_LON)}
    assert e["accuracy_m"] == pytest.approx(8.5)
    # Stored as the device sent it (same instant, whatever zone it's rendered in).
    assert datetime.fromisoformat(e["captured_at"]) == datetime.fromisoformat("2026-09-26T14:32:00+05:30")
    assert e["submitted_at"] is not None  # server clock, not the client's
    assert 100 < e["distance_from_issue_m"] < 125  # 0.001 deg latitude ~ 111 m
    assert e["review_status"] == "pending_review"
    assert e["file_url"] == f"/api/evidence/{e['evidence_id']}/file"


def test_uploaded_file_is_recorded_as_upload_not_camera(client, ev):
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], capture_method="upload")
    assert resp.status_code == 201, resp.text
    assert resp.json()["capture_method"] == "upload"


def test_unknown_capture_method_rejected(client, ev):
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], capture_method="drone")
    assert resp.status_code == 422


def test_retry_with_same_submission_id_returns_the_first_row(client, ev, db_conn):
    sid = str(uuid.uuid4())
    first = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], submission_id=sid)
    again = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], submission_id=sid)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["evidence_id"] == first.json()["evidence_id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM evidence WHERE client_submission_id = %s", (sid,))
        assert cur.fetchone()[0] == 1


def test_second_initial_photo_for_a_report_is_rejected(client, ev):
    assert submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).status_code == 201
    assert submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).status_code == 409


def test_location_is_required(client, ev):
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], lat=None)
    assert resp.status_code == 422


def test_non_image_bytes_rejected_whatever_the_content_type(client, ev):
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"],
                  body=b"<html><script>alert(1)</script></html>")
    assert resp.status_code == 400


def test_evidence_window_is_enforced(client, ev, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("UPDATE reports SET evidence_due_at = now() - interval '1 day' WHERE id = %s",
                    (ev["reports"]["alice"],))
    db_conn.commit()
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"])
    assert resp.status_code == 403 and "window" in resp.json()["detail"]


def test_delayed_evidence_within_window_attaches_to_existing_report(client, ev, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("UPDATE reports SET reported_at = now() - interval '3 days', "
                    "evidence_due_at = now() + interval '4 days' WHERE id = %s", (ev["reports"]["alice"],))
    db_conn.commit()
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"])
    assert resp.status_code == 201 and resp.json()["report_id"] == ev["reports"]["alice"]


# --- Authorization -------------------------------------------------------------

def test_citizen_cannot_attach_to_or_see_another_citizens_evidence(client, ev):
    alice_ev = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).json()
    # Bob can't attach to Alice's report, list her issue's evidence, or fetch her photo.
    assert submit(client, ev["as"]("bob"), ev["issues"]["road_w1"], ev["reports"]["alice"]).status_code == 404
    assert client.get(f"/api/issues/{ev['issues']['road_w1']}/evidence", headers=ev["as"]("bob")).status_code == 404
    assert client.get(alice_ev["file_url"], headers=ev["as"]("bob")).status_code == 404


def test_evidence_file_is_private_and_served_only_through_the_api(client, ev):
    e = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).json()
    assert client.get(e["file_url"]).status_code == 401
    # Road issue in ward 1: the ward officer and the road department are in scope.
    for who in ("alice", "admin", "ward_officer", "dept_officer"):
        resp = client.get(e["file_url"], headers=ev["as"](who))
        assert resp.status_code == 200 and resp.content == JPEG, who
        assert resp.headers["content-type"] == "image/jpeg"
        assert "no-store" in resp.headers["cache-control"]
        assert resp.headers["x-content-type-options"] == "nosniff"


def test_out_of_scope_staff_cannot_fetch_evidence_file(client, ev):
    e = submit(client, ev["as"]("bob"), ev["issues"]["drain_w2"], ev["reports"]["bob"]).json()
    # Drainage in ward 2: outside both the ward-1 officer and the road department.
    for who in ("ward_officer", "dept_officer"):
        assert client.get(e["file_url"], headers=ev["as"](who)).status_code == 403, who


def test_staff_do_not_capture_evidence(client, ev):
    resp = submit(client, ev["as"]("admin"), ev["issues"]["road_w1"], ev["reports"]["alice"])
    assert resp.status_code == 403


def test_staff_see_evidence_only_in_scope(client, ev):
    submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"])
    submit(client, ev["as"]("bob"), ev["issues"]["drain_w2"], ev["reports"]["bob"])
    ok = client.get(f"/api/issues/{ev['issues']['road_w1']}/evidence", headers=ev["as"]("ward_officer"))
    assert ok.status_code == 200 and len(ok.json()) == 1
    out = client.get(f"/api/issues/{ev['issues']['drain_w2']}/evidence", headers=ev["as"]("ward_officer"))
    assert out.status_code == 403



def test_evidence_queue_lists_only_in_scope_and_filters_by_review(client, ev):
    mine = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).json()
    submit(client, ev["as"]("bob"), ev["issues"]["drain_w2"], ev["reports"]["bob"])
    queue = client.get("/api/evidence", headers=ev["as"]("ward_officer"))
    assert queue.status_code == 200
    assert [e["evidence_id"] for e in queue.json()] == [mine["evidence_id"]]
    assert client.get("/api/evidence", params={"review_status": "verified"},
                      headers=ev["as"]("ward_officer")).json() == []
    assert client.get("/api/evidence", headers=ev["as"]("alice")).status_code == 403

# --- Worker resolution evidence -----------------------------------------------

def test_assigned_worker_submits_resolution_and_before_after_stay_linked(client, ev, db_conn):
    road = ev["issues"]["road_w1"]
    with db_conn.cursor() as cur:
        cur.execute("UPDATE issues SET status = 'open', closed_at = NULL WHERE id = %s", (road,))
    db_conn.commit()
    before = submit(client, ev["as"]("alice"), road, ev["reports"]["alice"]).json()

    # Unassigned workers can't submit, and assignment is staff-only.
    assert submit(client, ev["as"]("worker"), road).status_code == 403
    assert client.post(f"/api/issues/{road}/assign", headers=ev["as"]("alice"),
                       json={"worker_user_id": ev["users"]["worker"].id}).status_code == 403
    assigned = client.post(f"/api/issues/{road}/assign", headers=ev["as"]("admin"),
                           json={"worker_user_id": ev["users"]["worker"].id})
    assert assigned.status_code == 200, assigned.text
    # Only a field worker can be assigned.
    assert client.post(f"/api/issues/{road}/assign", headers=ev["as"]("admin"),
                       json={"worker_user_id": ev["users"]["alice"].id}).status_code == 400

    after = submit(client, ev["as"]("worker"), road, lat=ISSUE_LAT, lon=ISSUE_LON)
    assert after.status_code == 201, after.text
    assert after.json()["actor_type"] == "worker" and after.json()["evidence_type"] == "resolution"
    assert after.json()["distance_from_issue_m"] < 1
    assert submit(client, ev["as"]("other_worker"), road).status_code == 403

    # The worker sees the citizen's before photo; staff see both, in order.
    assert client.get(before["file_url"], headers=ev["as"]("worker")).status_code == 200
    chain = client.get(f"/api/issues/{road}/evidence", headers=ev["as"]("admin")).json()
    assert [e["evidence_type"] for e in chain] == ["initial_report", "resolution"]
    detail = client.get(f"/api/issues/{road}", headers=ev["as"]("admin")).json()
    assert detail["assigned_worker_id"] == ev["users"]["worker"].id
    assert [e["evidence_id"] for e in detail["evidence"]] == [before["evidence_id"], after.json()["evidence_id"]]


def test_field_worker_list_is_staff_only(client, ev):
    assert client.get("/api/field-workers", headers=ev["as"]("alice")).status_code == 403
    ids = [w["id"] for w in client.get("/api/field-workers", headers=ev["as"]("admin")).json()]
    assert ev["users"]["worker"].id in ids and ev["users"]["alice"].id not in ids


def test_worker_cannot_submit_after_issue_is_closed(client, ev):
    road = ev["issues"]["road_w1"]  # world creates it closed
    client.post(f"/api/issues/{road}/assign", headers=ev["as"]("admin"),
                json={"worker_user_id": ev["users"]["worker"].id})
    assert submit(client, ev["as"]("worker"), road).status_code == 409


# --- Staff review ----------------------------------------------------------------

def test_staff_review_is_recorded_and_notes_stay_internal(client, ev):
    e = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).json()
    assert client.post(f"/api/evidence/{e['evidence_id']}/review", headers=ev["as"]("alice"),
                       json={"review_status": "verified"}).status_code == 403
    resp = client.post(f"/api/evidence/{e['evidence_id']}/review", headers=ev["as"]("ward_officer"),
                       json={"review_status": "verified", "note": "matches site photo from survey"})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "verified" and resp.json()["reviewed_at"] is not None
    mine = client.get(f"/api/issues/{ev['issues']['road_w1']}/evidence", headers=ev["as"]("alice")).json()
    assert mine[0]["review_status"] == "verified" and mine[0]["review_note"] is None


# --- Evidence status: optional, never "false" -----------------------------------

def test_new_report_gets_a_stamped_evidence_window(client, ev, db_conn):
    resp = client.post("/api/reports", headers=ev["as"]("alice"),
                       json={"raw_text": f"Streetlight not working near the bus stop {ev['tag']}"})
    assert resp.status_code == 201, resp.text
    report = resp.json()["report"]
    assert report["evidence_status"] == "pending"
    with db_conn.cursor() as cur:
        cur.execute("SELECT evidence_due_at - reported_at FROM reports WHERE id = %s", (report["id"],))
        assert cur.fetchone()[0].days == 7



def test_report_without_photo_is_pending_not_false(client, ev):
    mine = client.get("/api/me/reports", headers=ev["as"]("alice")).json()
    report = next(r for r in mine if r["report_id"] == ev["reports"]["alice"])
    assert report["evidence_status"] == "pending" and report["evidence_due_at"] is not None


def test_alternative_verification_path(client, ev):
    rid = ev["reports"]["alice"]
    assert client.post(f"/api/reports/{rid}/alternative-verifications", headers=ev["as"]("alice"),
                       json={"channel": "phone"}).status_code == 403
    started = client.post(f"/api/reports/{rid}/alternative-verifications", headers=ev["as"]("ward_officer"),
                          json={"channel": "phone", "notes": "called reporter"})
    assert started.status_code == 201 and started.json()["status"] == "initiated"
    done = client.post(f"/api/alternative-verifications/{started.json()['id']}/complete",
                       headers=ev["as"]("ward_officer"), json={"status": "confirmed"})
    assert done.status_code == 200 and done.json()["completed_at"] is not None
    detail = client.get(f"/api/issues/{ev['issues']['road_w1']}", headers=ev["as"]("admin")).json()
    report = next(r for r in detail["reports"] if r["id"] == rid)
    assert report["evidence_status"] == "alternative_confirmed"
    assert detail["alternative_verifications"][0]["channel"] == "phone"
    # Out-of-scope staff can't start one.
    assert client.post(f"/api/reports/{ev['reports']['bob']}/alternative-verifications",
                       headers=ev["as"]("ward_officer"), json={"channel": "phone"}).status_code == 403


# --- Reverification window ----------------------------------------------------------

def test_close_opens_reverification_window_and_dispute_needs_no_photo(client, ev, db_conn):
    road = ev["issues"]["road_w1"]
    with db_conn.cursor() as cur:
        cur.execute("UPDATE issues SET status = 'open', closed_at = NULL WHERE id = %s", (road,))
    db_conn.commit()
    closed = client.post(f"/api/issues/{road}/close", headers=ev["as"]("admin"))
    assert closed.status_code == 200
    detail = client.get(f"/api/issues/{road}", headers=ev["as"]("admin")).json()
    assert detail["reverification_due_at"] is not None

    # JSON body only - no photo is asked for.
    resp = client.post(f"/api/issues/{road}/feedback", headers=ev["as"]("alice"),
                       json={"resolved_confirmed": False, "comment": "pothole is back after rain"})
    assert resp.status_code == 201 and resp.json()["issue_status"] == "reopened"


def test_feedback_after_reverification_window_is_rejected(client, ev, db_conn):
    road = ev["issues"]["road_w1"]
    with db_conn.cursor() as cur:
        cur.execute("UPDATE issues SET reverification_due_at = now() - interval '1 day' WHERE id = %s", (road,))
    db_conn.commit()
    resp = client.post(f"/api/issues/{road}/feedback", headers=ev["as"]("alice"), json={"resolved_confirmed": False})
    assert resp.status_code == 409 and "window" in resp.json()["detail"]


# --- Supabase Storage backend ------------------------------------------------------

@pytest.fixture
def storage_stub(monkeypatch):
    """A stand-in for Supabase Storage's object API, so the bucket code path
    runs for real over HTTP without a Supabase project."""
    class Objects(dict):
        signed: list  # request bodies of each signed-URL call

    objects, seen_auth, signed = Objects(), [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _auth_ok(self):
            seen_auth.append(self.headers.get("Authorization"))
            return self.headers.get("Authorization") == "Bearer service-key" and self.headers.get("apikey") == "service-key"

        def do_POST(self):
            if not self._auth_ok():
                return self.send_error(401)
            if self.path.startswith("/storage/v1/object/sign/"):
                key = self.path.replace("/object/sign/", "/object/", 1)
                if key not in objects:
                    return self.send_error(404)
                signed.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                reply = json.dumps({"signedURL": self.path[len("/storage/v1"):] + "?token=signed-token"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(reply)
                return
            objects[self.path] = (self.headers["Content-Type"], self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()

        def do_GET(self):
            if not self._auth_ok() or self.path not in objects:
                return self.send_error(404)
            mime, body = objects[self.path]
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("SUPABASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setenv("EVIDENCE_BUCKET", "complaint-images")
    objects.signed = signed
    yield objects
    server.shutdown()


def test_photos_go_to_the_private_bucket_when_supabase_is_configured(client, ev, storage_stub, tmp_path):
    e = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"])
    assert e.status_code == 201, e.text
    [(path, (mime, body))] = storage_stub.items()
    issue = ev["issues"]["road_w1"]
    assert path.startswith(f"/storage/v1/object/complaint-images/issues/{issue}/") and mime == "image/jpeg"
    assert body == JPEG
    assert not any(tmp_path.iterdir())  # nothing written to local disk
    served = client.get(e.json()["file_url"], headers=ev["as"]("admin"))
    assert served.status_code == 200 and served.content == JPEG
    assert client.get(e.json()["file_url"], headers=ev["as"]("bob")).status_code == 404


def test_staff_get_a_short_lived_signed_url_for_bucket_photos(client, ev, storage_stub):
    e = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).json()
    url_endpoint = f"/api/evidence/{e['evidence_id']}/url"
    resp = client.get(url_endpoint, headers=ev["as"]("admin"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    [path] = [p for p in storage_stub]
    assert body["url"] == f"{os.environ['SUPABASE_URL']}{path.replace('/object/', '/object/sign/', 1)}?token=signed-token"
    assert body["expires_in"] == 300 and storage_stub.signed == [{"expiresIn": 300}]
    # The owner may see their own photo; everyone else is refused before anything is signed.
    assert client.get(url_endpoint, headers=ev["as"]("alice")).status_code == 200
    assert client.get(url_endpoint, headers=ev["as"]("bob")).status_code == 404
    assert client.get(url_endpoint).status_code == 401
    assert len(storage_stub.signed) == 2


def test_signed_url_is_null_when_photos_are_on_local_disk(client, ev):
    e = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"]).json()
    resp = client.get(f"/api/evidence/{e['evidence_id']}/url", headers=ev["as"]("admin"))
    assert resp.status_code == 200 and resp.json() == {"url": None, "expires_in": None}


def test_storage_outage_is_retryable_and_leaves_no_row(client, ev, db_conn, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:9")  # nothing listens here
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    sid = str(uuid.uuid4())
    resp = submit(client, ev["as"]("alice"), ev["issues"]["road_w1"], ev["reports"]["alice"], submission_id=sid)
    assert resp.status_code == 503
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM evidence WHERE client_submission_id = %s", (sid,))
        assert cur.fetchone()[0] == 0
