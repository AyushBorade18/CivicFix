"""POST /api/chat/turn - the CivicFix Assistant.

Signed-in or not: a guest can look up public issues and draft a report, but
sending one, tracking reports and every staff command need an account, and
staff mode needs a staff role from our database. The logs record what
happened (intent, role, latency, outcome) - never what the citizen wrote.
"""
import json
import logging
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import verify_token
from app.chat.engine import error_response, handle_turn
from app.chat.schemas import ChatRequest, ChatResponse
from app.db import get_db
from app.users import CurrentUser, get_user

router = APIRouter()
log = logging.getLogger("civicfix.chat")
_bearer = HTTPBearer(auto_error=False)

# ponytail: in-process sliding window - one API worker today. Move to Redis
# (or the proxy) if the API ever runs more than one process.
RATE_LIMIT_TURNS = 30
RATE_LIMIT_WINDOW_S = 60
_turns: dict[str, deque] = defaultdict(deque)


def optional_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
                  db=Depends(get_db)) -> Optional[CurrentUser]:
    """None for a guest. A token that is present but invalid is still a 401 -
    a bad token never silently downgrades to guest."""
    if creds is None:
        return None
    user = get_user(db, verify_token(creds.credentials)["sub"])
    if user is not None and not user.is_active:
        raise HTTPException(status_code=403, detail="account is deactivated")
    return user  # verified identity without an account yet: treated as a guest


def _rate_limit(key: str) -> None:
    now = time.monotonic()
    window = _turns[key]
    while window and now - window[0] > RATE_LIMIT_WINDOW_S:
        window.popleft()
    if len(window) >= RATE_LIMIT_TURNS:
        raise HTTPException(status_code=429, detail="too many messages - please wait a minute")
    window.append(now)


@router.post("/api/chat/turn", response_model=ChatResponse)
def chat_turn(req: ChatRequest, request: Request, db=Depends(get_db),
              user: Optional[CurrentUser] = Depends(optional_user)):
    _rate_limit(f"user:{user.id}" if user else f"ip:{request.client.host if request.client else 'unknown'}")
    started = time.monotonic()
    outcome = "ok"
    try:
        response = handle_turn(db, user, req)
    except Exception:
        # Never a 500 into the chat: roll back, say so, keep the draft.
        log.exception("chat turn failed conversation=%s", req.state.conversation_id)
        db.rollback()
        response, outcome = error_response(req, "an internal error"), "error"
    log.info(json.dumps({
        "event": "chat_turn", "conversation": req.state.conversation_id,
        "role": user.role if user else "guest", "surface": req.surface,
        "action": req.action, "intent": response.intent, "step": response.state.step,
        "cards": [c.type for c in response.cards], "outcome": outcome,
        "latency_ms": round((time.monotonic() - started) * 1000),
    }))
    return response
