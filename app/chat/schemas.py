"""Wire format of POST /api/chat/turn.

The server keeps no conversation: the state travels with every request. It
holds only the caller's own draft, and each turn re-checks identity and
scope from the token and the database, so an edited state can't reach
anything the caller couldn't reach through the normal API anyway.
"""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Same shape serve_photo accepts: only a file our own upload endpoint wrote.
PHOTO_URL_PATTERN = r"^/api/photos/[0-9a-f]{32}\.(jpg|png|webp)$"

Step = Literal["idle", "confirm_report", "await_description", "await_category", "await_location",
               "await_landmark", "await_photo", "review", "await_issue_number"]
Lang = Literal["en", "hi", "mr", "hinglish"]


class Draft(BaseModel):
    """The complaint being put together. `text` is the citizen's own words,
    never rewritten; what will actually be sent is shown before sending."""
    text: str = Field("", max_length=2000)
    category: Optional[str] = Field(None, max_length=40)
    landmark: Optional[str] = Field(None, max_length=200)
    since: Optional[str] = Field(None, max_length=80)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_label: Optional[str] = Field(None, max_length=200)
    location_done: bool = False
    photo_url: Optional[str] = Field(None, pattern=PHOTO_URL_PATTERN)
    photo_done: bool = False


class ChatState(BaseModel):
    conversation_id: str = Field(default_factory=lambda: uuid.uuid4().hex, pattern=r"^[0-9a-f]{32}$")
    step: Step = "idle"
    lang: Lang = "en"
    lang_locked: bool = False
    draft: Draft = Field(default_factory=Draft)
    issue_id: Optional[int] = Field(None, ge=1)  # the issue the conversation is about


class ChatRequest(BaseModel):
    message: Optional[str] = Field(None, max_length=1000)
    action: Optional[str] = Field(None, max_length=40, pattern=r"^[a-z_]+$")
    value: Optional[str] = Field(None, max_length=60)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    photo_url: Optional[str] = Field(None, pattern=PHOTO_URL_PATTERN)
    # Which app the widget is in. Admin mode also needs a staff role - the
    # surface alone never unlocks anything.
    surface: Literal["citizen", "admin"] = "citizen"
    state: ChatState = Field(default_factory=ChatState)


class ChatAction(BaseModel):
    """A button. `reply` posts action/value back; `location`, `pin` and `photo`
    make the client collect that first; `link` navigates; `sign_in` shows sign-in."""
    kind: Literal["reply", "location", "pin", "photo", "link", "sign_in"] = "reply"
    label: str
    action: Optional[str] = None
    value: Optional[str] = None
    href: Optional[str] = None


class CardRow(BaseModel):
    label: str
    value: str


class CardFactor(BaseModel):
    label: str
    points: Optional[int] = None  # staff only: the term's contribution out of 100


class CardEvidence(BaseModel):
    label: str
    detail: str


class CardItem(BaseModel):
    title: str
    meta: str
    action: Optional[str] = None
    value: Optional[str] = None


class ChatCard(BaseModel):
    type: Literal["issue", "priority", "work", "outcome", "summary", "briefing", "verification", "history", "list"]
    title: str
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    tone: Optional[Literal["high", "med", "low", "neutral", "warn"]] = None
    rows: list[CardRow] = []
    factors: list[CardFactor] = []
    steps: list[CardRow] = []
    items: list[CardItem] = []
    evidence: list[CardEvidence] = []  # "View evidence": the source records behind the card
    note: Optional[str] = None
    href: Optional[str] = None
    href_label: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    cards: list[ChatCard] = []
    actions: list[ChatAction] = []
    state: ChatState
    intent: str
