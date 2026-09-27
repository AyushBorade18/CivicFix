"""CivicFix Assistant: language and intent rules, the citizen report flow
end to end through the real pipeline, staff commands and their scope, and
the safety rules (no invented records, no accusations, graceful failure).

Runs against civicfix_test with real RS256 tokens. Only the network-bound
steps are replaced: translation, text geocoding and the LLM triage call.
"""
import io
import json
import re
import uuid
from pathlib import Path

import pytest
from PIL import Image

import app.api.chat as chat_api
from app.chat import nlu
from app.chat.engine import compose_report_text
from app.chat.messages import t
from app.chat.schemas import Draft
from app.users import create_user
from tests.test_auth import auth, auth_env, client, make_token, signing_key  # noqa: F401

FORBIDDEN = re.compile(r"\b(fraud|corrupt\w*|guilty|scam|responsible for)\b", re.IGNORECASE)
COMPLAINT = "Water is logged on the road outside the municipal school gate since yesterday, children walk through it"


# --- Language and intent (no database) -------------------------------------------

@pytest.mark.parametrize("text, lang", [
    ("There is a huge pothole near the bus stop on Baner Road.", "en"),
    ("School ke saamne road pe bohot paani jama hai since yesterday.", "hinglish"),
    ("Road pe pothole hai near school.", "hinglish"),
    ("सड़क पर बहुत बड़ा गड्ढा है", "hi"),
    ("इथे पाणी खूप साचलं आहे.", "mr"),
    ("पावसामुळे रस्ता पूर्ण खराब झाला आहे.", "mr"),
    ("ithe khup paani sachla aahe", "mr"),
])
def test_reply_language_follows_the_citizen(text, lang):
    assert nlu.detect_chat_language(text) == lang


def test_short_messages_keep_the_current_language():
    assert nlu.detect_chat_language("ok", previous="mr") == "mr"
    assert nlu.detect_chat_language("12", previous="hinglish") == "hinglish"


def test_explicit_language_request():
    assert nlu.requested_language("please reply in Marathi") == "mr"
    assert nlu.requested_language("हिंदी में बताइए") == "hi"
    assert nlu.requested_language("the road near the english school") is None


@pytest.mark.parametrize("text, ref", [("#PMC-1042", 1042), ("status of CF-12?", 12), ("issue 7", 7),
                                        ("#33 kab hoga", 33), ("pothole near school", None)])
def test_issue_references(text, ref):
    assert nlu.issue_ref(text) == ref


def test_waterlogging_is_drainage_even_when_the_road_is_mentioned():
    # The classifier reads this as pothole_road (0.91); waterlogging is a drainage failure.
    for text in ("School ke saamne road pe bohot paani jama hai", "इथे पाणी खूप साचलं आहे", "water standing on the road"):
        assert nlu.category_from_words(text) == "drainage_sewage"
    assert nlu.category_from_words("pothole on the main road") == "pothole_road"
    assert nlu.category_from_words("something is wrong") is None


@pytest.mark.parametrize("text, intent", [
    ("What needs my attention today?", "briefing"),
    ("Show me today's critical drainage issues.", "list"),
    ("Why is CF-1042 in verification?", "explain"),
    ("Which issues are approaching SLA breach?", "deadlines"),
    ("Show me recurring issues in my ward.", "recurring"),
    ("What complaints are linked to project 5512?", "work"),
])
def test_admin_intents(text, intent):
    assert nlu.admin_intent(text, has_issue_context=False) == intent


def test_report_text_keeps_the_citizens_words_and_adds_only_category_and_landmark():
    d = Draft(text="Kal se paani jama hai", category="drainage_sewage", landmark="Baner Road")
    assert compose_report_text(d) == "Drainage / sewage: Kal se paani jama hai Near Baner Road."
    assert compose_report_text(Draft(text="Pothole outside my gate", category="pothole_road")) == "Pothole outside my gate"


# --- API fixtures ----------------------------------------------------------------

world_extra_issues: list[int] = []  # issues a test seeds directly; `world` deletes them


@pytest.fixture(autouse=True)
def offline_pipeline(monkeypatch):
    """Everything real except the network calls, which get their documented
    failure values: no translation, no text geocode, triage says 'review'."""
    monkeypatch.setattr("app.api.main.translate_to_english", lambda text, lang: None)
    monkeypatch.setattr("app.api.main.resolve_report_location", lambda text, conn=None: (None, None, None, None, None))
    monkeypatch.setattr("app.api.main.triage", lambda raw, translated: {
        "verdict": "review", "category": "other", "reason": "test", "model": None, "prompt_version": "test"})
    monkeypatch.setattr("app.ingest.geocode.geocode", lambda query, **kw: None)
    chat_api._turns.clear()


@pytest.fixture
def world(db_conn):
    """Citizens A and B, a ward officer for ward w (and not ward x), a system
    admin, and a point inside ward w. Deletes everything they create."""
    tag = uuid.uuid4().hex[:8]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id, ST_Y(ST_PointOnSurface(geom)), ST_X(ST_PointOnSurface(geom)) FROM wards "
                    "ORDER BY id LIMIT 2")
        (w, lat, lon), (x, _, _) = cur.fetchall()
    users = {name: create_user(db_conn, f"test|chat|{name}|{tag}", role) for name, role in [
        ("a", "citizen"), ("b", "citizen"), ("officer", "ward_officer"), ("admin", "system_admin")]}
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO user_wards (user_id, ward_id) VALUES (%s, %s)", (users["officer"].id, w))
    db_conn.commit()

    yield {"users": users, "ward": w, "other_ward": x, "point": (lat, lon)}

    ids = [u.id for u in users.values()]
    with db_conn.cursor() as cur:
        cur.execute("SELECT DISTINCT issue_id FROM reports WHERE reporter_user_id = ANY(%s)", (ids,))
        issues = [r[0] for r in cur.fetchall()] + world_extra_issues
        cur.execute("DELETE FROM alternative_verifications WHERE report_id IN "
                    "(SELECT id FROM reports WHERE issue_id = ANY(%s))", (issues,))
        cur.execute("DELETE FROM signals WHERE issue_id = ANY(%s)", (issues,))
        cur.execute("DELETE FROM matches WHERE issue_id = ANY(%s)", (issues,))
        cur.execute("DELETE FROM feedback WHERE issue_id = ANY(%s)", (issues,))
        cur.execute("DELETE FROM reports WHERE issue_id = ANY(%s)", (issues,))
        cur.execute("DELETE FROM issues WHERE id = ANY(%s)", (issues,))
        cur.execute("DELETE FROM audit_log WHERE actor_user_id = ANY(%s)", (ids,))
        cur.execute("DELETE FROM user_wards WHERE user_id = ANY(%s)", (ids,))
        cur.execute("DELETE FROM users WHERE id = ANY(%s)", (ids,))
    db_conn.commit()
    world_extra_issues.clear()


@pytest.fixture
def chat(client, make_token, world):
    """chat(who, **turn) -> response JSON. who=None is a guest. Every reply
    and card is checked for accusatory wording on the way out."""
    def _chat(who, state=None, **turn):
        headers = auth(make_token(world["users"][who].external_auth_id)) if who else {}
        body = {**turn, **({"state": state} if state else {})}
        res = client.post("/api/chat/turn", json=body, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert not FORBIDDEN.search(json.dumps(data, ensure_ascii=False)), data
        return data
    return _chat


def report_via_chat(chat, who, point, text=COMPLAINT, send_action="send"):
    """The full citizen flow: describe -> confirm -> pin -> skip photo -> review -> send."""
    r = chat(who, message=text)
    assert r["state"]["step"] == "confirm_report"
    r = chat(who, r["state"], action="report_it")
    assert r["state"]["step"] == "await_location"
    r = chat(who, r["state"], action="location", value="pin", latitude=point[0], longitude=point[1])
    assert r["state"]["step"] == "await_photo"
    review = chat(who, r["state"], action="skip_photo")
    assert review["state"]["step"] == "review"
    sent = chat(who, review["state"], action=send_action)
    return review, sent


# --- Citizen ---------------------------------------------------------------------

def test_guest_can_draft_but_must_sign_in_to_send(chat):
    r = chat(None, message="There is a huge pothole near the bus stop on Baner Road.")
    assert r["state"]["step"] == "confirm_report" and r["state"]["lang"] == "en"
    assert "Road / pothole" in r["reply"]
    r = chat(None, r["state"], action="report_it")
    assert [a["kind"] for a in r["actions"]] == ["sign_in"]
    assert r["state"]["draft"]["text"].startswith("There is a huge pothole")  # draft kept


@pytest.mark.parametrize("text, lang, category_label", [
    ("School ke saamne road pe bohot paani jama hai since yesterday.", "hinglish", "Drainage / paani jama"),
    ("सड़क पर बहुत बड़ा गड्ढा है स्कूल के पास", "hi", "सड़क / गड्ढा"),
    ("इथे पाणी खूप साचलं आहे, शाळेजवळ", "mr", "गटार / पाणी साचणे"),
])
def test_complaint_understood_and_answered_in_the_citizens_language(chat, text, lang, category_label):
    r = chat("a", message=text)
    assert r["state"]["lang"] == lang
    assert category_label in r["reply"]
    assert r["state"]["draft"]["text"] == text  # the original words, untouched


def test_missing_location_is_asked_for_and_only_that(chat):
    r = chat("a", message=COMPLAINT)
    r = chat("a", r["state"], action="report_it")
    assert r["reply"] == t("ask_location", "en")
    assert {a["kind"] for a in r["actions"]} >= {"location", "pin"}


def test_pin_outside_pmc_is_refused_not_snapped(chat):
    r = chat("a", message=COMPLAINT)
    r = chat("a", r["state"], action="report_it")
    r = chat("a", r["state"], action="location", latitude=19.07, longitude=72.87)  # Mumbai
    assert r["reply"] == t("location_outside", "en")
    assert r["state"]["draft"]["latitude"] is None and not r["state"]["draft"]["location_done"]


def test_failed_geocoding_degrades_honestly(chat):
    r = chat("a", message=COMPLAINT)
    r = chat("a", r["state"], action="report_it")
    r = chat("a", r["state"], action="landmark")
    r = chat("a", r["state"], message="Behind the old banyan tree")
    assert r["reply"] == t("location_fail", "en")
    assert r["state"]["draft"]["latitude"] is None  # no invented coordinates
    assert "skip_location" in [a["action"] for a in r["actions"]]  # can still send with the locality words


def test_landmark_that_geocodes_inside_a_ward_is_used(chat, world, monkeypatch):
    monkeypatch.setattr("app.ingest.geocode.geocode", lambda query, **kw: world["point"])
    r = chat("a", message=COMPLAINT)
    r = chat("a", r["state"], action="report_it")
    r = chat("a", r["state"], message="Baner Road bus stop")
    assert r["state"]["draft"]["location_done"] and r["state"]["draft"]["landmark"] == "Baner Road bus stop"
    assert r["state"]["step"] == "await_photo"


def test_first_report_starts_an_issue_and_a_duplicate_joins_it(chat, world):
    _, first = report_via_chat(chat, "a", world["point"])
    issue_id = first["state"]["issue_id"]
    assert f"#PMC-{issue_id}" in first["reply"]
    assert first["cards"][0]["type"] == "issue"

    review, second = report_via_chat(chat, "b", world["point"])
    assert "appears to describe the same problem" in review["reply"]
    assert review["cards"][1]["title"].startswith(f"#PMC-{issue_id}")
    assert [a["action"] for a in review["actions"]][:2] == ["send", "send_separate"]
    assert second["state"]["issue_id"] == issue_id
    assert t("sent_joined", "en", code=f"#PMC-{issue_id}", others=1) in second["reply"]
    # Citizens see the reasons for the priority, never the points.
    priority = next(c for c in second["cards"] if c["type"] == "priority")
    assert all(f["points"] is None for f in priority["factors"]) and "/100" not in priority["badge"]


def test_report_separately_starts_its_own_issue(chat, world):
    _, first = report_via_chat(chat, "a", world["point"])
    _, second = report_via_chat(chat, "b", world["point"], send_action="send_separate")
    assert second["state"]["issue_id"] != first["state"]["issue_id"]


def test_photo_is_attached_as_evidence(chat, client, make_token, world, db_conn):
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (90, 90, 90)).save(buf, format="JPEG")
    up = client.post("/api/uploads/photo", files={"file": ("p.jpg", buf.getvalue(), "image/jpeg")},
                     headers=auth(make_token(world["users"]["a"].external_auth_id)))
    assert up.status_code == 201, up.text
    photo_url = up.json()["photo_url"]
    try:
        r = chat("a", message=COMPLAINT)
        r = chat("a", r["state"], action="report_it")
        r = chat("a", r["state"], action="location", latitude=world["point"][0], longitude=world["point"][1])
        r = chat("a", r["state"], action="photo", photo_url=photo_url)
        assert r["state"]["draft"]["photo_url"] == photo_url and r["state"]["step"] == "review"
        sent = chat("a", r["state"], action="send")
        assert sent["state"]["issue_id"]
    finally:
        Path("data/uploads", Path(photo_url).name).unlink(missing_ok=True)
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM photo_uploads WHERE filename = %s", (Path(photo_url).name,))
        db_conn.commit()


def test_unknown_or_forged_photo_is_not_attached(chat, client):
    r = chat("a", message=COMPLAINT)
    r = chat("a", r["state"], action="photo", photo_url="/api/photos/" + "0" * 32 + ".jpg")
    assert r["state"]["draft"]["photo_url"] is None
    bad = client.post("/api/chat/turn", json={"action": "photo", "photo_url": "/etc/passwd"})
    assert bad.status_code == 422


def test_invalid_input_is_rejected_or_answered_with_the_menu(chat, client):
    assert client.post("/api/chat/turn", json={"message": "x" * 1001}).status_code == 422
    assert client.post("/api/chat/turn", json={"action": "DROP TABLE"}).status_code == 422
    r = chat(None, action="does_not_exist")
    assert r["reply"] == t("menu", "en")


def test_track_shows_only_my_own_reports(chat, world):
    _, sent = report_via_chat(chat, "a", world["point"])
    mine = chat("a", action="track")
    assert f"#PMC-{sent['state']['issue_id']}" in json.dumps(mine)
    theirs = chat("b", action="track")
    assert theirs["reply"] == t("track_none", "en")


def test_priority_reasons_only_for_reporters(chat, world):
    _, sent = report_via_chat(chat, "a", world["point"])
    issue_id = sent["state"]["issue_id"]
    assert chat("b", action="priority", value=str(issue_id))["reply"] == t("priority_private", "en")
    mine = chat("a", action="priority", value=str(issue_id))
    assert mine["cards"][0]["type"] == "priority"


def test_unknown_issue_is_never_invented(chat):
    r = chat("a", message="what is happening with #PMC-987654321")
    assert r["reply"] == t("issue_not_found", "en", code="#PMC-987654321")
    assert r["cards"] == []


def test_no_public_work_means_saying_so(chat, world):
    _, sent = report_via_chat(chat, "a", world["point"])
    r = chat("a", sent["state"], action="work")
    if r["cards"]:  # a real MPLADS work can match in this ward; then it must be a real record
        assert r["cards"][0]["type"] == "work" and "MPLADS record #" in json.dumps(r["cards"][0])
    else:
        assert r["reply"] == t("work_none", "en")


def test_recurrence_after_closure_reopens_for_verification(chat, client, make_token, world):
    _, first = report_via_chat(chat, "a", world["point"])
    issue_id = first["state"]["issue_id"]
    closed = client.post(f"/api/issues/{issue_id}/close",
                         headers=auth(make_token(world["users"]["admin"].external_auth_id)))
    assert closed.status_code == 200

    review, sent = report_via_chat(chat, "b", world["point"])
    assert f"#PMC-{issue_id}" in review["reply"] and "recurrence evidence" in review["reply"]
    assert sent["state"]["issue_id"] == issue_id
    assert sent["reply"].startswith(t("sent_reopened", "en", code=f"#PMC-{issue_id}"))


def test_resolved_is_not_verified_until_the_reporter_confirms(chat, client, make_token, world):
    _, first = report_via_chat(chat, "a", world["point"])
    issue_id = first["state"]["issue_id"]
    client.post(f"/api/issues/{issue_id}/close", headers=auth(make_token(world["users"]["admin"].external_auth_id)))

    opened = chat("a", action="start")
    assert "Resolved is a status; verified is evidence" in opened["reply"]
    card = chat("a", action="issue", value=str(issue_id))["cards"][0]
    assert card["badge"].startswith("Marked resolved - awaiting citizen verification")

    disputed = chat("a", action="closed_answer", value=f"still:{issue_id}")
    assert disputed["reply"] == t("thanks_disputed", "en")
    assert disputed["cards"][0]["badge"] == "Reopened for verification"


def test_confirm_before_dispatch_is_asked_only_when_staff_opened_a_check(chat, client, make_token, world, db_conn):
    _, first = report_via_chat(chat, "a", world["point"])
    assert "Before a crew is sent" not in chat("a", action="start")["reply"]

    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM reports WHERE reporter_user_id = %s", (world["users"]["a"].id,))
        report_id = cur.fetchone()[0]
    started = client.post(f"/api/reports/{report_id}/alternative-verifications", json={"channel": "other"},
                          headers=auth(make_token(world["users"]["officer"].external_auth_id)))
    assert started.status_code == 201, started.text
    vid = started.json()["id"]

    opened = chat("a", action="start")
    assert t("confirm_dispatch", "en", code=f"#PMC-{first['state']['issue_id']}") in opened["reply"]
    # Another citizen can't answer it.
    assert chat("b", action="dispatch_answer", value=f"present:{vid}")["reply"] == t("not_sure", "en")
    assert chat("a", action="dispatch_answer", value=f"present:{vid}")["reply"] == t("thanks_recorded", "en")
    with db_conn.cursor() as cur:
        cur.execute("SELECT status, completed_by FROM alternative_verifications WHERE id = %s", (vid,))
        assert cur.fetchone() == ("confirmed", world["users"]["a"].id)
        cur.execute("SELECT count(*) FROM audit_log WHERE action = 'alternative_verification.reporter_answer' "
                    "AND target_id = %s", (str(vid),))
        assert cur.fetchone()[0] == 1


# --- Staff -----------------------------------------------------------------------

def test_admin_surface_needs_a_staff_role(chat):
    citizen = chat("a", surface="admin", message="What needs my attention today?")
    assert "Today's summary" not in citizen["reply"]
    assert citizen["intent"] != "briefing"


def test_briefing_is_scoped_and_names_the_top_case(chat, world):
    report_via_chat(chat, "a", world["point"])
    r = chat("officer", surface="admin", message="What needs my attention today?")
    assert r["intent"] == "briefing" and r["cards"][0]["type"] == "briefing"
    assert r["reply"].startswith("Today's summary for")


def test_explain_shows_points_inside_scope_and_nothing_outside(chat, world, db_conn):
    _, sent = report_via_chat(chat, "a", world["point"])
    issue_id = sent["state"]["issue_id"]
    r = chat("officer", surface="admin", message=f"Why is #PMC-{issue_id} prioritized?")
    priority = next(c for c in r["cards"] if c["type"] == "priority")
    assert "/100" in priority["badge"] and all(f["points"] is not None for f in priority["factors"])
    assert any(c["type"] == "verification" for c in r["cards"])

    with db_conn.cursor() as cur:  # an issue in a ward this officer doesn't hold
        cur.execute("INSERT INTO issues (category, ward_id, status, report_count, first_reported, last_reported, "
                    "priority_score) VALUES ('pothole_road', %s, 'open', 1, now(), now(), 0.9) RETURNING id",
                    (world["other_ward"],))
        other = cur.fetchone()[0]
        cur.execute("INSERT INTO reports (raw_text, reported_at, category, issue_id, is_synthetic) "
                    "VALUES ('pothole', now(), 'pothole_road', %s, false)", (other,))
    db_conn.commit()
    world_extra_issues.append(other)
    outside = chat("officer", surface="admin", message=f"why #PMC-{other}")
    assert outside["reply"] == f"#PMC-{other} is outside your ward/department scope, so its details aren't shown."
    assert outside["cards"] == []


def test_route_action_goes_through_the_api_and_is_audited(chat, world, db_conn):
    _, sent = report_via_chat(chat, "a", world["point"])
    issue_id = sent["state"]["issue_id"]
    r = chat("officer", surface="admin", action="route", value=str(issue_id))
    assert r["reply"].startswith(f"Routed #PMC-{issue_id} to PMC")
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit_log WHERE action = 'issue.route' AND target_id = %s", (str(issue_id),))
        assert cur.fetchone()[0] == 1


def test_contradictory_evidence_is_named_not_resolved(chat, world, db_conn):
    _, sent = report_via_chat(chat, "a", world["point"])
    issue_id = sent["state"]["issue_id"]
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO feedback (issue_id, resolved_confirmed, submitted_at, is_synthetic) "
                    "VALUES (%s, true, now(), false), (%s, false, now(), false)", (issue_id, issue_id))
    db_conn.commit()
    r = chat("admin", surface="admin", action="issue", value=str(issue_id))
    assert "Evidence points in different directions" in r["reply"] and "Human review is needed" in r["reply"]


def test_deadlines_never_claim_an_sla_that_does_not_exist(chat):
    r = chat("officer", surface="admin", message="Which issues are approaching SLA breach?")
    assert r["reply"].startswith("CivicFix has no SLA targets configured")


def test_unknown_work_is_never_invented(chat):
    r = chat("admin", surface="admin", message="What complaints are linked to work 987654321?")
    assert r["reply"] == "I don't have a record of MPLADS work #987654321."


# --- Reliability -----------------------------------------------------------------

def test_backend_failure_keeps_the_draft_and_says_so(client, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("database went away")
    monkeypatch.setattr(chat_api, "handle_turn", boom)
    state = {"step": "review", "lang": "hi", "draft": {"text": "सड़क पर गड्ढा है", "category": "pothole_road"}}
    r = client.post("/api/chat/turn", json={"action": "send", "state": state})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "error" and "CivicFix सेवा" in body["reply"]
    assert body["state"]["draft"]["text"] == "सड़क पर गड्ढा है"


def test_invalid_token_is_rejected_not_downgraded_to_guest(client):
    r = client.post("/api/chat/turn", json={"action": "start"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_rate_limit(client):
    for _ in range(chat_api.RATE_LIMIT_TURNS):
        assert client.post("/api/chat/turn", json={"action": "menu"}).status_code == 200
    assert client.post("/api/chat/turn", json={"action": "menu"}).status_code == 429
