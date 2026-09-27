"""CivicFix Assistant: one conversation turn in, one reply out.

Citizen flow (the state machine lives in `_next`):
  idle -> confirm_report -> [await_category] -> await_location [-> await_landmark]
       -> await_photo -> review -> send -> idle
Staff on the admin surface get officer commands instead (briefing, explain,
verification queue, deadlines, public-work links, route).

Replies are fixed templates (app/chat/messages.py) filled only with values
from app/chat/tools.py or an existing API function. Nothing is generated, so
a reply cannot contain an ID, score or date that is not on record, and every
action goes through the same function - and the same scope check and audit
row - as the rest of the app.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from app.chat import nlu, tools
from app.chat.messages import category_label, site_label, t
from app.chat.schemas import (CardEvidence, CardFactor, CardItem, CardRow, ChatAction, ChatCard, ChatRequest,
                              ChatResponse, ChatState, Draft)
from app.core.clustering import COSINE_THRESHOLD
from app.core.routing import route_issue
from app.users import CurrentUser

log = logging.getLogger("civicfix.chat")

# The prefix the report form already puts in front of the citizen's words
# (web/src/api/types.ts CATEGORY_LABELS). It is what steers the classifier to
# the category the citizen confirmed; the summary card shows the exact text.
_REPORT_PREFIX = {
    "pothole_road": "Pothole / road", "drainage_sewage": "Drainage / sewage", "water_supply": "Water supply",
    "streetlight": "Streetlight", "garbage_waste": "Garbage / waste", "footpath": "Footpath",
    "traffic_signage": "Traffic signage",
}
_CHIP_CATEGORIES = ("pothole_road", "drainage_sewage", "water_supply", "streetlight", "garbage_waste",
                    "footpath", "traffic_signage", "other")


def code(issue_id: int) -> str:
    return f"#PMC-{issue_id}"  # same format as the admin UI (issueCode in ws.tsx)


def _date(d) -> str:
    return f"{d:%d %b %Y}" if d else "—"


def _inr(cost) -> str:
    if cost is None:
        return "—"
    cost = float(cost)
    if cost >= 1e7:
        return f"₹{cost / 1e7:.2f} Cr"
    if cost >= 1e5:
        return f"₹{cost / 1e5:.1f} L"
    return f"₹{cost:,.0f}"


@dataclass
class Turn:
    db: object
    user: Optional[CurrentUser]
    req: ChatRequest
    state: ChatState
    staff_mode: bool = False
    intent: str = "menu"
    lines: list[str] = field(default_factory=list)
    cards: list[ChatCard] = field(default_factory=list)
    actions: list[ChatAction] = field(default_factory=list)

    @property
    def lang(self) -> str:
        return self.state.lang

    @property
    def draft(self) -> Draft:
        return self.state.draft

    def say(self, key: str, **values) -> None:
        self.lines.append(t(key, self.lang, **values))

    def text(self, line: str) -> None:
        self.lines.append(line)

    def button(self, key: str, action: Optional[str] = None, value: Optional[str] = None, kind: str = "reply") -> None:
        self.actions.append(ChatAction(kind=kind, label=t(key, self.lang), action=action, value=value))

    def custom(self, label: str, action: Optional[str] = None, value: Optional[str] = None,
               kind: str = "reply", href: Optional[str] = None) -> None:
        self.actions.append(ChatAction(kind=kind, label=label, action=action, value=value, href=href))

    def issue_href(self, issue_id: int) -> str:
        return f"/issues/{issue_id}" if self.staff_mode else f"/citizen/issues/{issue_id}"

    def response(self) -> ChatResponse:
        return ChatResponse(reply="\n\n".join(self.lines), cards=self.cards, actions=self.actions,
                            state=self.state, intent=self.intent)


def handle_turn(db, user: Optional[CurrentUser], req: ChatRequest) -> ChatResponse:
    # Admin mode needs BOTH the admin surface and a staff role from the
    # database; a citizen sending surface="admin" just gets the citizen flow.
    staff_mode = req.surface == "admin" and user is not None and user.is_staff
    turn = Turn(db, user, req, req.state.model_copy(deep=True), staff_mode=staff_mode)
    message = (req.message or "").strip()
    if staff_mode:
        turn.state.lang = "en"
        _admin(turn, message)
        return turn.response()
    if message:
        requested = nlu.requested_language(message)
        if requested:
            turn.state.lang, turn.state.lang_locked = requested, True
            turn.intent = "language"
            turn.say("lang_set")
            _menu_buttons(turn)
            return turn.response()
        if not turn.state.lang_locked:
            turn.state.lang = nlu.detect_chat_language(message, turn.state.lang)
    _citizen(turn, message)
    return turn.response()


def error_response(req: ChatRequest, detail: str) -> ChatResponse:
    """Backend failure: say so, keep the caller's state (and draft) as it was."""
    return ChatResponse(reply=t("service_error", req.state.lang, detail=detail), state=req.state, intent="error")


# --- Citizen ------------------------------------------------------------------

def _citizen(turn: Turn, message: str) -> None:
    action = turn.req.action
    if action:
        turn.intent = action
        CITIZEN_ACTIONS.get(action, _menu)(turn)
        return
    if not message:
        _menu(turn)
        return

    step = turn.state.step
    intent = nlu.citizen_intent(message, turn.state.issue_id is not None)
    if step in ("await_location", "await_landmark") and intent not in ("issue", "track", "cancel"):
        turn.intent = "landmark"
        _landmark(turn, message)
        return
    if step == "await_description" and intent not in ("issue", "track", "cancel"):
        turn.intent = "complaint"
        _understand(turn, message)
        return
    if step == "await_issue_number" and message.lstrip("#").isdigit():
        turn.intent = "issue"
        _show_issue(turn, int(message.lstrip("#")))
        return
    if step == "await_category":
        category = nlu.category_from_words(message)
        if category:
            turn.intent = "set_category"
            turn.draft.category = category
            _next(turn)
            return
    # A short reply in the middle of a report ("no", "ok") must not throw the
    # draft away as a new complaint: repeat the pending question instead.
    if step in ("confirm_report", "await_photo", "review") and intent == "complaint" and len(message.split()) < 4:
        turn.intent = "reprompt"
        if step == "confirm_report":
            _understood(turn)
        else:
            _next(turn)
        return

    turn.intent = intent
    if intent == "issue":
        _show_issue(turn, nlu.issue_ref(message))
    elif intent == "cancel":
        _cancel(turn)
    elif intent == "track":
        _track(turn)
    elif intent == "work":
        _work(turn)
    elif intent == "history":
        _history(turn)
    elif intent == "priority":
        _priority(turn)
    elif intent == "greeting":
        _menu(turn)
    else:
        _understand(turn, message)


def _menu_buttons(turn: Turn) -> None:
    turn.button("b_report", "report")
    turn.button("b_track", "track")
    turn.button("b_similar", "similar")
    turn.button("b_check", "check")


def _menu(turn: Turn) -> None:
    turn.state.step = "idle"
    turn.say("menu")
    _menu_buttons(turn)


def _start(turn: Turn) -> None:
    """Panel opened. Ask a pending question only if a record is waiting on this citizen."""
    turn.state.step = "idle"
    turn.say("menu")
    prompt = tools.pending_prompt(turn.db, turn.user) if turn.user is not None else None
    if prompt and prompt["kind"] == "dispatch":
        turn.say("confirm_dispatch", code=code(prompt["issue_id"]))
        vid = prompt["verification_id"]
        turn.button("b_still_there", "dispatch_answer", f"present:{vid}")
        turn.button("b_fixed", "dispatch_answer", f"fixed:{vid}")
        turn.button("b_not_sure", "dispatch_answer", "unsure")
    elif prompt:
        iid = prompt["issue_id"]
        turn.say("confirm_closed", code=code(iid), date=_date(prompt["closed_at"]))
        turn.button("b_fixed", "closed_answer", f"fixed:{iid}")
        turn.button("b_still_there", "closed_answer", f"still:{iid}")
        turn.button("b_not_sure", "closed_answer", "unsure")
    _menu_buttons(turn)


def _cancel(turn: Turn) -> None:
    turn.state.draft = Draft()
    turn.state.step = "idle"
    turn.say("cancelled")
    _menu_buttons(turn)


def _start_report(turn: Turn, intro: str = "ask_describe") -> None:
    turn.state.draft = Draft()
    turn.state.step = "await_description"
    turn.say(intro)


def _check(turn: Turn) -> None:
    turn.state.step = "await_issue_number"
    turn.say("ask_issue_number")


def _suggest_category(text: str) -> Optional[str]:
    """The real classifier, except for the one measured blind spot (standing
    water on a road reads as pothole_road). A suggestion only: the citizen
    confirms or changes it before anything is sent."""
    if nlu.mentions_waterlogging(text):
        return "drainage_sewage"
    from app.nlp.classify import classify
    category, _ = classify(text)
    return category if category != "other" else nlu.category_from_words(text)


def _location_clue(db, text: str) -> Optional[str]:
    """A landmark worth repeating back. Low-confidence spaCy guesses are
    dropped (it reads Hinglish 'hai' as a place), never shown as fact."""
    from app.nlp.location import extract_location_phrase
    phrase, confidence = extract_location_phrase(text, conn=db)
    return phrase if phrase and confidence >= 0.6 and len(phrase.split()) <= 4 else None


def _understand(turn: Turn, text: str) -> None:
    if len(text) < 10 or len(text.split()) < 3:
        turn.state.step = "await_description"
        turn.say("ask_describe")
        return
    # Keep a photo/pin given before the words; a fresh complaint starts clean.
    base = turn.draft if turn.state.step == "await_description" else Draft()
    turn.state.draft = base.model_copy(update={"text": text[:2000], "category": _suggest_category(text),
                                               "since": nlu.duration_phrase(text)})
    if turn.draft.category is None:
        turn.state.step = "await_category"
        turn.say("ask_category")
        _category_buttons(turn)
        return
    _understood(turn, _location_clue(turn.db, text))


def _understood(turn: Turn, clue: Optional[str] = None) -> None:
    turn.state.step = "confirm_report"
    where = t("where", turn.lang, clue=clue) if clue else ""
    turn.say("understood", category=category_label(turn.draft.category, turn.lang), where=where)
    turn.button("b_report_it", "report_it")
    turn.button("b_change_category", "change_category")
    turn.button("b_not_now", "cancel")


def _category_buttons(turn: Turn) -> None:
    for category in _CHIP_CATEGORIES:
        turn.custom(category_label(category, turn.lang), "set_category", category)


def _location_buttons(turn: Turn) -> None:
    turn.button("b_use_location", "location", "gps", kind="location")
    turn.button("b_drop_pin", "location", "pin", kind="pin")
    turn.button("b_type_landmark", "landmark")


def _next(turn: Turn) -> None:
    """Ask for the first missing piece - only that - or show the review."""
    d = turn.draft
    if not d.text:  # a photo or pin can come first; keep it and ask for the words
        turn.state.step = "await_description"
        turn.say("ask_describe")
    elif not d.category:
        turn.state.step = "await_category"
        turn.say("ask_category")
        _category_buttons(turn)
    elif turn.user is None:
        turn.state.step = "confirm_report"
        turn.say("sign_in")
        turn.button("b_sign_in", "report_it", kind="sign_in")
    elif not d.location_done:
        turn.state.step = "await_location"
        turn.say("ask_location")
        _location_buttons(turn)
        turn.button("b_skip", "skip_location")
    elif not d.photo_done:
        turn.state.step = "await_photo"
        turn.say("ask_photo")
        turn.button("b_add_photo", "photo", kind="photo")
        turn.button("b_skip", "skip_photo")
    else:
        _review(turn)


def _set_category(turn: Turn) -> None:
    category = nlu.valid_category(turn.req.value)
    if category:
        turn.draft.category = category
    _next(turn)


def _change_category(turn: Turn) -> None:
    turn.state.step = "await_category"
    turn.say("ask_category")
    _category_buttons(turn)


def _location_point(turn: Turn) -> None:
    """GPS or a dropped pin. Kept only if it falls inside a PMC ward."""
    from app.api.main import ward_containing
    lat, lon = turn.req.latitude, turn.req.longitude
    ward_id = ward_containing(turn.db, lat, lon) if lat is not None and lon is not None else None
    if ward_id is None:
        turn.state.step = "await_location"
        turn.say("location_outside" if lat is not None else "location_fail")
        _location_buttons(turn)
        turn.button("b_send_without", "skip_location")
        return
    d = turn.draft
    d.latitude, d.longitude, d.location_done = lat, lon, True
    d.location_label = tools.ward_name(turn.db, ward_id) or f"Ward {ward_id}"
    turn.say("location_ok", ward=d.location_label)
    _next(turn)


def _ask_landmark(turn: Turn) -> None:
    turn.state.step = "await_landmark"
    turn.say("ask_landmark")


def _landmark(turn: Turn, text: str) -> None:
    """A typed street or landmark. Geocoded here so the reply is honest about
    whether it was found; if not, nothing is guessed - the citizen can drop a
    pin or send with the locality words (the pipeline then falls back to ward
    level, confidence 0.4, per the graceful-degradation rule)."""
    from app.api.main import ward_containing
    from app.ingest.geocode import geocode
    d = turn.draft
    d.landmark = text[:200]
    point = geocode(f"{text}, Pune, Maharashtra, India")
    ward_id = ward_containing(turn.db, *point) if point else None
    if ward_id is None:
        turn.state.step = "await_location"
        turn.say("location_fail")
        _location_buttons(turn)
        turn.button("b_send_without", "skip_location")
        return
    d.latitude, d.longitude, d.location_done = point[0], point[1], True
    d.location_label = f"{text} · {tools.ward_name(turn.db, ward_id) or f'Ward {ward_id}'}"
    turn.say("location_ok", ward=d.location_label)
    _next(turn)


def _skip_location(turn: Turn) -> None:
    turn.draft.location_done = True
    turn.say("location_skipped")
    _next(turn)


def _photo(turn: Turn) -> None:
    """A photo already accepted by POST /api/uploads/photo (validated,
    re-encoded, EXIF stripped). Evidence only - it never changes severity."""
    url = turn.req.photo_url
    if url:
        with turn.db.cursor() as cur:
            cur.execute("SELECT 1 FROM photo_uploads WHERE filename = %s", (Path(url).name,))
            known = cur.fetchone() is not None
        if known:
            turn.draft.photo_url, turn.draft.photo_done = url, True
            turn.say("photo_ok")
            _next(turn)
            return
    turn.state.step = "await_photo"
    turn.say("ask_photo")
    turn.button("b_add_photo", "photo", kind="photo")
    turn.button("b_skip", "skip_photo")


def _skip_photo(turn: Turn) -> None:
    turn.draft.photo_done = True
    _next(turn)


def compose_report_text(d: Draft) -> str:
    """Exactly what is sent: the citizen's words, unchanged, with the
    confirmed category in front (unless they already said it) and their
    landmark after - the same convention as the report form."""
    kind = _REPORT_PREFIX.get(d.category or "", "")
    said = kind and kind.split(" ")[0].lower() in d.text.lower()
    parts = [f"{kind}:" if kind and not said else "", d.text.strip(),
             f"Near {d.landmark.strip()}." if d.landmark else ""]
    return " ".join(p for p in parts if p)


def _review(turn: Turn) -> None:
    turn.state.step = "review"
    d = turn.draft
    composed = compose_report_text(d)
    rows = [CardRow(label=t("l_category", turn.lang), value=category_label(d.category, turn.lang)),
            CardRow(label=t("l_location", turn.lang), value=d.location_label or d.landmark or t("v_not_given", turn.lang))]
    if d.since:
        rows.append(CardRow(label=t("l_since", turn.lang), value=d.since))
    if d.photo_url:
        rows.append(CardRow(label=t("l_photo", turn.lang), value=t("v_attached", turn.lang)))
    rows.append(CardRow(label=t("l_text", turn.lang), value=composed))
    turn.cards.append(ChatCard(type="summary", title=t("t_summary", turn.lang), rows=rows))

    try:
        preview = tools.preview(turn.db, composed, d.latitude, d.longitude)
    except HTTPException as exc:
        turn.db.rollback()
        turn.say("service_error", detail=str(exc.detail))
        preview = None
    except Exception:
        log.exception("chat preview failed conversation=%s", turn.state.conversation_id)
        turn.db.rollback()
        turn.say("preview_failed")
        preview = None

    match = tools.issue_row(turn.db, preview["match_issue_id"]) if preview and preview["match_issue_id"] else None
    prior = (tools.issue_row(turn.db, preview["recurrence_issue_id"])
             if preview and not match and preview["recurrence_issue_id"] else None)
    if match:
        turn.say("match_many" if match["report_count"] > 1 else "match_one", n=match["report_count"])
        turn.cards.append(_issue_card(turn, match))
        turn.button("b_add_to_issue", "send")
        turn.button("b_report_separately", "send_separate")
    else:
        if prior:
            turn.say("recurrence", code=code(prior["id"]), date=_date(prior["closed_at"]))
            turn.cards.append(_issue_card(turn, prior))
        elif preview:
            turn.say("no_match")
        turn.button("b_send", "send")
    turn.button("b_cancel", "cancel")


def _send(turn: Turn) -> None:
    _submit(turn, separate=False)


def _send_separate(turn: Turn) -> None:
    _submit(turn, separate=True)


def _submit(turn: Turn, separate: bool) -> None:
    """Sends through create_report itself - the same pipeline, rules and
    ownership as the report form. The citizen always saw the text first."""
    if turn.user is None or turn.state.step != "review":
        _next(turn)  # signed out, or a stale button from an earlier turn
        return
    from app.api.main import create_report
    from app.api.schemas import ReportCreateRequest
    d = turn.draft
    payload = ReportCreateRequest(raw_text=compose_report_text(d), photo_url=d.photo_url, latitude=d.latitude,
                                  longitude=d.longitude, separate_issue=separate)
    try:
        result = create_report(payload, db=turn.db, user=turn.user)
    except HTTPException as exc:
        turn.db.rollback()
        turn.say("service_error", detail=str(exc.detail))
        turn.button("b_send", "send")
        turn.button("b_cancel", "cancel")
        return

    turn.state.draft = Draft()
    turn.state.step = "idle"
    if result.held_for_review:
        turn.say("sent_held")
        turn.button("b_track", "track")
        return

    row = tools.issue_row(turn.db, result.issue_id)
    turn.state.issue_id = result.issue_id
    issue_code = code(result.issue_id)
    if row["status"] == "reopened":
        turn.say("sent_reopened", code=issue_code)
    elif result.joined_existing_issue:
        turn.say("sent_joined", code=issue_code, others=row["report_count"] - 1)
    else:
        turn.say("sent_new", code=issue_code)
    turn.cards.append(_issue_card(turn, row))
    _append_priority(turn, row, show_intro=True)
    _append_work(turn, result.issue_id, quiet_if_none=True)
    turn.button("b_history", "history")
    turn.button("b_track", "track")
    turn.custom(t("b_view_issue", turn.lang), kind="link", href=turn.issue_href(result.issue_id))


def _issue_card(turn: Turn, row: dict) -> ChatCard:
    key, values = tools.status_key(row)
    status = t(key, turn.lang, **values)
    return ChatCard(
        type="issue", title=f"{code(row['id'])} · {category_label(row['category'], turn.lang)}",
        badge=status, tone="warn" if row["status"] == "reopened" else "neutral",
        rows=[
            CardRow(label=t("l_reports", turn.lang), value=str(row["report_count"])),
            CardRow(label=t("l_ward", turn.lang), value=row["ward_name"] or "—"),
            CardRow(label=t("l_first", turn.lang), value=_date(row["first_reported"])),
            CardRow(label=t("l_last", turn.lang), value=_date(row["last_reported"])),
        ],
        evidence=[CardEvidence(
            label=f"Civic Issue {code(row['id'])}",
            detail=f"{row['report_count']} report(s) grouped by the clustering rule: same category, nearby, within "
                   f"7 days, text similarity ≥ {COSINE_THRESHOLD}. Reporters' identities are never shown.",
        )],
        href=turn.issue_href(row["id"]), href_label=t("b_view_issue", turn.lang),
    )


def _issue_or_not_found(turn: Turn, issue_id: Optional[int]) -> Optional[dict]:
    if issue_id is None:
        turn.state.step = "await_issue_number"
        turn.say("ask_issue_number")
        return None
    row = tools.issue_row(turn.db, issue_id)
    if row is None:
        turn.say("issue_not_found", code=code(issue_id))
    return row


def _context_issue_id(turn: Turn) -> Optional[int]:
    value = turn.req.value
    return int(value) if value and value.isdigit() else turn.state.issue_id


def _show_issue(turn: Turn, issue_id: Optional[int] = None) -> None:
    issue_id = issue_id if issue_id is not None else _context_issue_id(turn)
    turn.state.step = "idle"
    row = _issue_or_not_found(turn, issue_id)
    if row is None:
        return
    turn.state.issue_id = issue_id
    turn.say("issue_record", code=code(issue_id))
    turn.cards.append(_issue_card(turn, row))
    if (turn.user is not None and turn.user.is_staff) or tools.is_reporter(turn.db, turn.user, issue_id):
        turn.button("b_why_priority", "priority")
    turn.button("b_related_work", "work")
    turn.button("b_history", "history")
    turn.custom(t("b_view_issue", turn.lang), kind="link", href=turn.issue_href(issue_id))


def _priority_card(turn: Turn, row: dict, staff: bool) -> Optional[ChatCard]:
    """The stored formula breakdown, term by term. Citizens see the reasons;
    staff also see each term's points. Nothing is recomputed or estimated."""
    bd = row.get("priority_breakdown")
    if not bd or row.get("priority_score") is None:
        return None
    contributions = {k: bd["weights"][k] * bd["terms"][k] for k in bd["terms"]}
    factors = []
    for term in sorted(contributions, key=contributions.get, reverse=True):
        if contributions[term] <= 0:
            continue
        if term == "severity":
            label = t("f_severity", turn.lang, band=t(f"band_{bd['severity_band']}", turn.lang))
        elif term == "exposure":
            site = (bd.get("exposure_detail") or {}).get("matched_site")
            if not site:
                continue
            label = t("f_exposure", turn.lang, site=site_label(site["kind"], turn.lang))
        elif term == "recurrence":
            label = t("f_recurrence", turn.lang, n=bd["recurrence_count"])
        else:
            label = t("f_time", turn.lang, d=bd["time_open_days"])
        factors.append(CardFactor(label=label, points=round(contributions[term] * 100) if staff else None))
    level = tools.band(row["priority_score"])
    badge = t(f"lv_{level}", turn.lang) + (f" · {round(row['priority_score'] * 100)}/100" if staff else "")
    return ChatCard(type="priority", title=t("t_priority", turn.lang), badge=badge, tone=level, factors=factors,
                    note=t("priority_formula", turn.lang),
                    evidence=[CardEvidence(label="Formula (app/core/priority.py)", detail=bd["explanation"])])


def _append_priority(turn: Turn, row: dict, show_intro: bool) -> None:
    staff = turn.user is not None and turn.user.is_staff
    card = _priority_card(turn, row, staff)
    if card is None:
        turn.say("priority_none")
        return
    if show_intro:
        turn.say("priority_intro", level=t(f"lv_{tools.band(row['priority_score'])}", turn.lang))
    turn.cards.append(card)


def _priority(turn: Turn) -> None:
    row = _issue_or_not_found(turn, _context_issue_id(turn))
    if row is None:
        return
    turn.state.issue_id = row["id"]
    staff = turn.user is not None and turn.user.is_staff
    if not staff and not tools.is_reporter(turn.db, turn.user, row["id"]):
        turn.say("priority_private")
        return
    _append_priority(turn, row, show_intro=True)


def _work_card(turn: Turn, w: dict) -> ChatCard:
    lang = turn.lang
    distance = (f"{w['distance_m']:.0f} m" if w["distance_m"] is not None else t("v_ward_level", lang))
    return ChatCard(
        type="work", title=t("t_work", lang), subtitle=w["work_name"],
        badge=(w["work_status"] or "—").replace("_", " "),
        rows=[
            CardRow(label=t("l_agency", lang), value=w["agency"] or "—"),
            CardRow(label=t("l_recorded_status", lang), value=(w["work_status"] or "—").replace("_", " ")),
            CardRow(label=t("l_completed", lang), value=_date(w["completed_on"])),
            CardRow(label=t("l_cost", lang), value=_inr(w["cost"])),
            CardRow(label=t("l_distance", lang), value=distance),
            CardRow(label=t("l_source", lang), value=f"MPLADS record #{w['work_id']}"),
        ],
        evidence=[CardEvidence(label=t("l_why_linked", lang), detail=w["match_reason"])] + [
            CardEvidence(label=f"Verification signal #{s['id']} · {s['rule_name']}",
                         detail=f"{s['explanation']} Source records: {s['source_record_ids']}")
            for s in w["signals"]
        ],
        note=t("work_found", lang),
    )


def _outcome_card(turn: Turn, row: dict, w: dict) -> ChatCard:
    lang = turn.lang
    return ChatCard(type="outcome", title=t("t_outcome", lang), tone="warn" if w["signals"] else "neutral", steps=[
        CardRow(label=t("s_first", lang), value=_date(row["first_reported"])),
        CardRow(label=t("s_work", lang), value=w["work_name"]),
        CardRow(label=t("l_completed", lang), value=_date(w["completed_on"])),
        CardRow(label=t("l_after", lang), value=str(w["reports_after"])),
        CardRow(label=t("l_verification", lang), value=t("v_flagged" if w["signals"] else "v_not_flagged", lang)),
    ])


def _append_work(turn: Turn, issue_id: int, quiet_if_none: bool = False) -> Optional[dict]:
    w = tools.related_work(turn.db, issue_id)
    if w is None:
        if not quiet_if_none:
            turn.say("work_none")
        return None
    turn.say("work_found")
    if w["completed_on"] is not None:
        turn.say("work_after", date=_date(w["completed_on"]), n=w["reports_after"])
    if w["signals"]:
        turn.say("work_flagged")
    turn.cards.append(_work_card(turn, w))
    row = tools.issue_row(turn.db, issue_id)
    if row is not None:
        turn.cards.append(_outcome_card(turn, row, w))
    return w


def _work(turn: Turn) -> None:
    row = _issue_or_not_found(turn, _context_issue_id(turn))
    if row is None:
        return
    turn.state.issue_id = row["id"]
    _append_work(turn, row["id"])


def _history(turn: Turn) -> None:
    row = _issue_or_not_found(turn, _context_issue_id(turn))
    if row is None:
        return
    turn.state.issue_id = row["id"]
    lang = turn.lang
    h = tools.history(turn.db, row)
    if h is None:
        turn.say("history_no_location")
        return
    label = category_label(row["category"], lang)
    if not h["ids"]:
        turn.say("history_none", category=label, r=h["radius_m"])
    else:
        turn.say("history_found", r=h["radius_m"], k=len(h["ids"]), category=label, closed=h["closed"],
                 reopened=h["reopened"])
    if row["recurrence_count"]:
        turn.say("history_self", n=row["recurrence_count"])
    if h["ids"] or row["recurrence_count"]:
        turn.cards.append(ChatCard(
            type="history", title=t("t_history", lang), subtitle=code(row["id"]),
            items=[CardItem(title=code(i), meta=label, action="issue", value=str(i)) for i in h["ids"][:8]],
            evidence=[CardEvidence(label="Rule", detail=f"Same category, within {h['radius_m']} m, first reported "
                                                        f"before {code(row['id'])} (app/core/recurrence.py radius).")],
        ))


def _track(turn: Turn) -> None:
    turn.state.step = "idle"
    if turn.user is None:
        turn.say("sign_in")
        turn.button("b_sign_in", "track", kind="sign_in")
        return
    rows = tools.my_reports(turn.db, turn.user)
    if not rows:
        turn.say("track_none")
        turn.button("b_report", "report")
        return
    turn.say("track_list")
    items = []
    for r in rows:
        key, values = tools.status_key(r)
        held = bool(r["held_as_spam"])
        items.append(CardItem(
            title=f"{code(r['id'])} · {category_label(r['category'], turn.lang)}" if not held
            else f"Report #{r['report_id']} · {category_label(r['category'], turn.lang)}",
            meta=f"{t(key, turn.lang, **values)} · {_date(r['reported_at'])}",
            action=None if held else "issue", value=None if held else str(r["id"]),
        ))
    turn.cards.append(ChatCard(type="list", title=t("t_reports", turn.lang), items=items))
    turn.state.issue_id = next((r["id"] for r in rows if not r["held_as_spam"]), None)


def _closed_answer(turn: Turn) -> None:
    """'Is it actually fixed?' - recorded through submit_feedback, which
    checks this user reported the issue and the reverification window."""
    answer, _, ident = (turn.req.value or "").partition(":")
    if answer not in ("fixed", "still") or not ident.isdigit() or turn.user is None:
        turn.say("not_sure")
        return
    from app.api.main import submit_feedback
    from app.api.schemas import FeedbackCreateRequest
    try:
        submit_feedback(int(ident), FeedbackCreateRequest(resolved_confirmed=answer == "fixed",
                                                          comment="Answered in CivicFix Assistant"),
                        db=turn.db, user=turn.user)
    except HTTPException as exc:
        turn.db.rollback()
        turn.say("service_error", detail=str(exc.detail))
        return
    turn.say("thanks_confirmed" if answer == "fixed" else "thanks_disputed")
    turn.state.issue_id = int(ident)
    row = tools.issue_row(turn.db, int(ident))
    if row is not None:
        turn.cards.append(_issue_card(turn, row))


def _dispatch_answer(turn: Turn) -> None:
    answer, _, ident = (turn.req.value or "").partition(":")
    if answer not in ("present", "fixed") or not ident.isdigit() or turn.user is None:
        turn.say("not_sure")
        return
    issue_id = tools.answer_dispatch_check(turn.db, turn.user, int(ident), still_present=answer == "present")
    turn.say("thanks_recorded" if issue_id is not None else "not_sure")


CITIZEN_ACTIONS = {
    "start": _start, "menu": _menu, "cancel": _cancel,
    "report": _start_report, "similar": lambda turn: _start_report(turn, "similar_intro"), "check": _check,
    "report_it": _next, "set_category": _set_category, "change_category": _change_category,
    "location": _location_point, "landmark": _ask_landmark, "skip_location": _skip_location,
    "photo": _photo, "skip_photo": _skip_photo, "send": _send, "send_separate": _send_separate,
    "track": _track, "issue": _show_issue, "priority": _priority, "work": _work, "history": _history,
    "closed_answer": _closed_answer, "dispatch_answer": _dispatch_answer,
}


# --- Staff (admin surface) ------------------------------------------------------

def _admin(turn: Turn, message: str) -> None:
    action = turn.req.action
    if action:
        turn.intent = action
        ADMIN_ACTIONS.get(action, _admin_menu)(turn)
        return
    if not message:
        _admin_menu(turn)
        return
    intent = nlu.admin_intent(message, turn.state.issue_id is not None)
    turn.intent = intent
    if intent == "explain":
        _explain(turn, nlu.issue_ref(message) or turn.state.issue_id)
    elif intent == "work":
        _work_links(turn, nlu.work_ref(message))
    elif intent == "deadlines":
        _deadlines(turn)
    elif intent == "verification":
        _verification(turn)
    elif intent == "history":
        _history(turn)
    elif intent in ("recurring", "list"):
        category = nlu.category_from_words(message)
        high = nlu.mentions_high_priority(message)
        if intent == "list" and not category and not high and nlu._has(message, nlu.ADMIN_BRIEFING):
            turn.intent = "briefing"
            _briefing(turn)
        else:
            _admin_list(turn, category=category, high=high, recurring=intent == "recurring")
    elif intent == "briefing":
        _briefing(turn)
    else:
        _admin_menu(turn)


def _admin_menu(turn: Turn) -> None:
    turn.text("Ask about today's priorities, an issue (\"why #PMC-12\"), the verification queue, upcoming "
              "deadlines, or a public work (\"work 5512\"). Answers come only from CivicFix records.")
    turn.custom("Today's priorities", "briefing")
    turn.custom("Verification queue", "verification")
    turn.custom("Deadlines & SLA risk", "deadlines")
    turn.custom("Search issues", "search")


def _search(turn: Turn) -> None:
    turn.text("Type an issue number (#PMC-12), a filter (\"critical drainage issues\", \"recurring issues\"), "
              "or a public work (\"work 5512\").")


def _no_scope(turn: Turn) -> bool:
    if tools.has_scope(turn.user):
        return False
    turn.text("No wards or departments are assigned to your account yet, so nothing is in your scope. "
              "A system administrator assigns scope.")
    return True


def _briefing(turn: Turn) -> None:
    if _no_scope(turn):
        return
    from app.api.admin import _scope_label
    b = tools.briefing(turn.db, turn.user)
    scope = _scope_label(turn.db, turn.user)
    turn.text(f"Today's summary for {scope}: {b['high']} high-priority open issue(s), {b['verification']} "
              f"verification case(s), and {b['deadlines']} reverification window(s) closing in the next "
              f"{tools.DEADLINE_WINDOW_DAYS} days.")
    turn.cards.append(ChatCard(
        type="briefing", title="Today's CivicFix summary", subtitle=scope,
        rows=[CardRow(label="High-priority open issues (≥ 70/100)", value=str(b["high"])),
              CardRow(label="Verification cases", value=str(b["verification"])),
              CardRow(label=f"Reverification windows closing ≤ {tools.DEADLINE_WINDOW_DAYS} days", value=str(b["deadlines"])),
              CardRow(label="Open issues", value=str(b["open"])),
              CardRow(label="Open and not yet routed", value=str(b["unrouted"]))],
        evidence=[CardEvidence(label="Verification case", detail="An open issue that was reopened after a resolution, "
                               "has citizen evidence pending review, or carries a public-work verification signal."),
                  CardEvidence(label="High priority", detail="priority_score ≥ 0.70, the same P1 cut-off as the Issues page.")],
    ))
    top = b["top_verification"]
    if top:
        turn.state.issue_id = top["id"]
        turn.text(f"The highest-priority verification case is {code(top['id'])} "
                  f"({category_label(top['category'], 'en')}, {top['ward_name'] or 'ward not set'}, "
                  f"priority {round((top['priority_score'] or 0) * 100)}/100).")
        turn.custom(f"Why {code(top['id'])}?", "issue", str(top["id"]))
    turn.custom("Open verification queue", kind="link", href="/verification")
    turn.custom("Deadlines & SLA risk", "deadlines")


def _list_card(title: str, rows: list[dict]) -> ChatCard:
    return ChatCard(type="list", title=title, items=[
        CardItem(title=f"{code(r['id'])} · {category_label(r['category'], 'en')}",
                 meta=f"{r['ward_name'] or 'Ward not set'} · {round((r['priority_score'] or 0) * 100)}/100 · "
                      f"{r['report_count']} report(s) · {r['status']}",
                 action="issue", value=str(r["id"]))
        for r in rows
    ])


def _admin_list(turn: Turn, category: Optional[str], high: bool, recurring: bool) -> None:
    if _no_scope(turn):
        return
    total, rows = tools.admin_issues(turn.db, turn.user, category=category,
                                     min_priority=tools.HIGH_PRIORITY if high else None, recurring=recurring)
    desc = " ".join(filter(None, ["high-priority" if high else "", "recurring" if recurring else "",
                                  category_label(category, "en").lower() if category else ""]))
    desc = f" {desc}" if desc else ""
    if total == 0:
        turn.text(f"No open{desc} issues in your scope right now.")
        return
    turn.text(f"{total} open{desc} issue(s) in your scope"
              + (f"; the top {len(rows)} by priority:" if total > len(rows) else ", by priority:"))
    turn.cards.append(_list_card("Issues", rows))
    turn.state.issue_id = rows[0]["id"]


def _verification(turn: Turn) -> None:
    if _no_scope(turn):
        return
    total, rows = tools.admin_issues(turn.db, turn.user, verification=True)
    if total == 0:
        turn.text("No open verification cases in your scope.")
    else:
        turn.text(f"{total} verification case(s) in your scope - reopened after a resolution, evidence pending "
                  f"review, or a public-work signal. Highest priority first:")
        turn.cards.append(_list_card("Verification cases", rows))
        turn.state.issue_id = rows[0]["id"]
    turn.custom("Open verification queue", kind="link", href="/verification")


def _deadlines(turn: Turn) -> None:
    if _no_scope(turn):
        return
    d = tools.deadlines(turn.db, turn.user)
    turn.text("CivicFix has no SLA targets configured, so it can't say which issues breach one. "
              "These are the real deadlines and ages on record:")
    items = [CardItem(title=f"{code(r['id'])} · {category_label(r['category'], 'en')}",
                      meta=f"Reverification window closes {_date(r['reverification_due_at'])} · {r['ward_name'] or '—'}",
                      action="issue", value=str(r["id"])) for r in d["windows"]]
    items += [CardItem(title=f"{code(r['id'])} · {category_label(r['category'], 'en')}",
                       meta=f"Open {r['age_days']} days · {r['ward_name'] or '—'} · "
                            f"{round((r['priority_score'] or 0) * 100)}/100",
                       action="issue", value=str(r["id"])) for r in d["oldest"]]
    if not d["windows"]:
        turn.text(f"No reverification windows close in the next {tools.DEADLINE_WINDOW_DAYS} days.")
    if items:
        turn.cards.append(ChatCard(type="list", title="Deadlines and oldest open issues", items=items))


def _work_links(turn: Turn, work_id: Optional[int]) -> None:
    if work_id is None:
        _search(turn)
        return
    w = tools.work_links(turn.db, turn.user, work_id)
    if w is None:
        turn.text(f"I don't have a record of MPLADS work #{work_id}.")
        return
    completed = f", recorded completed {_date(w['completed_on'])}" if w["completed_on"] else ""
    turn.text(f"MPLADS work #{work_id} '{w['work_name']}' ({(w['status'] or 'status not recorded').replace('_', ' ')}"
              f"{completed}). {len(w['issues'])} issue(s) in your scope are linked to it. A link is a "
              f"location/category relationship for human review, not a finding about the work.")
    turn.cards.append(ChatCard(type="work", title="Public work", subtitle=w["work_name"], rows=[
        CardRow(label="Agency", value=w["agency"] or "—"),
        CardRow(label="Recorded status", value=(w["status"] or "—").replace("_", " ")),
        CardRow(label="Recorded completion", value=_date(w["completed_on"])),
        CardRow(label="Sanctioned cost", value=_inr(w["cost"])),
        CardRow(label="Source", value=f"MPLADS record #{work_id}"),
    ], href=f"/works/{work_id}", href_label="Open work record"))
    if w["issues"]:
        turn.cards.append(_list_card("Linked issues", w["issues"]))


def _explain(turn: Turn, issue_id: Optional[int]) -> None:
    """Why an issue is where it is: formula, recurrence, public work, signals,
    citizen feedback, conflicts - and the human action the records point to.
    Goes through issue_detail, so a 404/403 there is a 404/403 here."""
    if issue_id is None:
        turn.text("Which issue? Type its number, for example #PMC-12.")
        return
    from app.api.main import issue_detail
    try:
        detail = issue_detail(issue_id, db=turn.db, user=turn.user)
    except HTTPException as exc:
        if exc.status_code == 403:
            turn.text(f"{code(issue_id)} is outside your ward/department scope, so its details aren't shown.")
        else:
            turn.text(f"I don't have verified information about {code(issue_id)}.")
        return
    row = tools.issue_row(turn.db, issue_id)
    turn.state.issue_id = issue_id
    key, values = tools.status_key(row)
    cat = category_label(row["category"], "en")
    turn.text(f"{code(issue_id)} · {cat} in {row['ward_name'] or 'an unplaced ward'}: {t(key, 'en', **values)}. "
              f"{row['report_count']} report(s) between {_date(row['first_reported'])} and {_date(row['last_reported'])}.")
    turn.cards.append(_issue_card(turn, row))

    priority = _priority_card(turn, row, staff=True)
    if priority is not None:
        turn.cards.append(priority)
        top = priority.factors[0] if priority.factors else None
        turn.text(f"Priority {round(row['priority_score'] * 100)}/100 ({priority.badge.split(' ·')[0]})"
                  + (f"; the largest factor is {top.label} (+{top.points})." if top else "."))
    if row["recurrence_count"]:
        turn.text(f"It has come back {row['recurrence_count']} time(s) after being marked resolved.")

    work = tools.related_work(turn.db, issue_id)
    if work is not None:
        turn.cards.append(_work_card(turn, work))
        turn.cards.append(_outcome_card(turn, row, work))
        if work["completed_on"] is not None:
            turn.text(f"Related public work: MPLADS #{work['work_id']}, recorded completed {_date(work['completed_on'])}; "
                      f"{work['reports_after']} report(s) on this issue came after that date. CivicFix does not "
                      f"assume the work resolved the problem.")

    confirmed = sum(1 for f in detail.feedback if f.resolved_confirmed)
    disputed = len(detail.feedback) - confirmed
    pending = sum(1 for e in detail.evidence if e.review_status == "pending_review")
    after_close = (sum(1 for r in detail.reports if r.reported_at > row["closed_at"])
                   if row["status"] == "closed" and row["closed_at"] else 0)
    conflicts = []
    if confirmed and disputed:
        conflicts.append(f"{confirmed} reporter confirmation(s) and {disputed} dispute(s) of the resolution")
    if after_close:
        conflicts.append(f"marked resolved on {_date(row['closed_at'])}, but {after_close} report(s) arrived afterwards")
    if conflicts:
        turn.text("Evidence points in different directions: " + "; ".join(conflicts) + ". Human review is needed.")

    actions = []
    if pending:
        actions.append(f"Review {pending} pending evidence item(s).")
    if work is not None and work["signals"]:
        actions.append("Compare the recorded public work with the complaint evidence and decide whether a field "
                       "verification is needed.")
    if row["status"] == "reopened":
        actions.append("Check on the ground whether the earlier resolution held before closing again.")
    agency = route_issue(row["category"])
    if row["status"] != "closed" and not row["routed_agency"]:
        actions.append(f"Route to {agency} (fixed category-to-department table).")
    if not actions:
        actions.append("No pending action is indicated by the records on file.")
    signals = [s for s in detail.signals if s.match_id is not None or s.rule_name == "CITIZEN_DISPUTED_RESOLUTION"]
    turn.cards.append(ChatCard(
        type="verification", title="Recommended human action",
        tone="warn" if signals or conflicts else "neutral",
        rows=[CardRow(label=f"{i + 1}", value=a) for i, a in enumerate(actions)],
        evidence=[CardEvidence(label=f"Signal #{s.signal_id} · {s.rule_name}",
                               detail=f"{s.explanation} Source records: {s.source_record_ids}") for s in signals]
        + [CardEvidence(label="Reports", detail=f"{len(detail.reports)} report(s): ids "
                                                f"{[r.id for r in detail.reports][:20]}")],
        note="These are evidence and rules, not conclusions. The decision stays with the reviewing officer.",
    ))
    turn.custom("Open issue", kind="link", href=f"/issues/{issue_id}")
    turn.custom("Verification queue", kind="link", href="/verification")
    if row["status"] != "closed" and not row["routed_agency"]:
        turn.custom(f"Route to {agency}", "route", str(issue_id))
    turn.custom("Has this happened before?", "history", str(issue_id))


def _admin_issue(turn: Turn) -> None:
    value = turn.req.value
    _explain(turn, int(value) if value and value.isdigit() else turn.state.issue_id)


def _route(turn: Turn) -> None:
    """Routing via the API's own endpoint function: same scope check, same
    signal row, same audit entry."""
    value = turn.req.value
    if not value or not value.isdigit():
        _search(turn)
        return
    from app.api.main import route_issue_endpoint
    try:
        result = route_issue_endpoint(int(value), db=turn.db, user=turn.user)
    except HTTPException as exc:
        turn.db.rollback()
        turn.text(f"Not routed: {exc.detail}.")
        return
    turn.state.issue_id = int(value)
    turn.text(f"Routed {code(int(value))} to {result.routed_agency}. The action is recorded in the audit log.")


ADMIN_ACTIONS = {
    "start": _admin_menu, "menu": _admin_menu, "briefing": _briefing, "verification": _verification,
    "deadlines": _deadlines, "search": _search, "issue": _admin_issue, "route": _route, "history": _history,
}
