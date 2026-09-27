"""What the citizen or officer said: language, intent, and the clues in it.

Deterministic on purpose. Keyword and regex rules can be read, tested and
argued with; nothing here invents a fact, it only routes to a database query.
Category and location still come from the real pipeline (app/nlp/*) - this
module only adds what that pipeline doesn't do: reply language and intent.
"""
import re
from typing import Optional

from app.categories import CIVIC_CATEGORIES
from app.nlp.language import detect_language

LANGS = ("en", "hi", "mr", "hinglish")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_WORD = re.compile(r"[a-zऀ-ॿ]+")

# Words that only one of the two Devanagari languages uses. langdetect
# confuses short Hindi/Marathi strings, so markers decide first.
_MARATHI = {"आहे", "आहेत", "इथे", "नाही", "झाला", "झाले", "झालं", "साचलं", "साचले", "आमच्या", "माझी", "माझ्या",
            "पाणी", "खूप", "रस्त्यावर", "केव्हा", "काय", "मध्ये", "पासून", "दिवसांपासून", "तक्रार"}
_HINDI = {"है", "हैं", "नहीं", "यहाँ", "यहां", "हमारे", "मेरी", "मेरा", "सड़क", "पानी", "बहुत", "क्या", "में",
          "से", "कब", "शिकायत", "दिनों"}
# Romanized Hindi (Hinglish) and romanized Marathi. English never uses these.
_HINGLISH = {"hai", "hain", "nahi", "nahin", "ke", "ki", "ka", "pe", "mein", "bahut", "bohot", "bahot",
             "paani", "pani", "sadak", "saamne", "samne", "kal", "raat", "hamare", "humare", "mera", "meri",
             "kya", "kab", "kahan", "abhi", "jama", "gaddha", "gadda", "kachra", "batti", "hua", "raha",
             "rahi", "kuch", "karo", "aur", "yahan", "wahan", "din", "se", "bhi", "koi"}
_ROMAN_MARATHI = {"aahe", "ahe", "khup", "ithe", "sachla", "sachle", "zala", "zhala", "amchya", "majhi",
                  "mazi", "kay", "nahiye", "pasun"}

_LANG_REQUEST = [
    (re.compile(r"\b(in\s+english|english\s+(me|mein|madhe|please)|reply\s+in\s+english)\b|^english$"), "en"),
    (re.compile(r"\b(in\s+hindi|hindi\s+(me|mein|please)|reply\s+in\s+hindi)\b|^hindi$|हिंदी में|हिन्दी में"), "hi"),
    (re.compile(r"\b(in\s+marathi|marathi\s+(madhe|madhye|please)|reply\s+in\s+marathi)\b|^marathi$|मराठीत|मराठीमध्ये"), "mr"),
]


def requested_language(text: str) -> Optional[str]:
    """'reply in Marathi', 'मराठीत बोला' -> an explicit, sticky choice."""
    t = text.strip().lower()
    for pattern, lang in _LANG_REQUEST:
        if pattern.search(t):
            return lang
    return None


def detect_chat_language(text: str, previous: str = "en") -> str:
    """Reply language for this message. Keeps the previous one for messages
    too short to tell ('ok', '12', a landmark name)."""
    t = text.lower()
    words = set(_WORD.findall(t))
    if _DEVANAGARI.search(t):
        mr, hi = len(words & _MARATHI), len(words & _HINDI)
        if mr != hi:
            return "mr" if mr > hi else "hi"
        guess = detect_language(text)
        return guess if guess in ("hi", "mr") else (previous if previous in ("hi", "mr") else "hi")
    if len(words) < 2:
        return previous
    roman_mr, hinglish = len(words & _ROMAN_MARATHI), len(words & _HINGLISH)
    if roman_mr and roman_mr * 2 >= hinglish:
        return "mr"
    if hinglish >= 2:
        return "hinglish"
    return "en"


# --- Intent ------------------------------------------------------------------

_ISSUE_REF = re.compile(r"(?:pmc|cf|issue|complaint|case)\s*[-#:]?\s*(\d{1,9})\b|#\s*(\d{1,9})\b", re.IGNORECASE)
_WORK_REF = re.compile(r"\b(?:work|project|pw|mplads)\s*[-#:]?\s*(\d{1,9})\b", re.IGNORECASE)


def issue_ref(text: str) -> Optional[int]:
    """'#PMC-12', 'CF-12', 'issue 12', '#12' -> 12."""
    m = _ISSUE_REF.search(text)
    return int(m.group(1) or m.group(2)) if m else None


def work_ref(text: str) -> Optional[int]:
    m = _WORK_REF.search(text)
    return int(m.group(1)) if m else None


def _has(text: str, words) -> bool:
    t = f" {text.lower()} "
    return any(w in t for w in words)


GREETING = (" hi ", " hello", " hey ", "namaste", "namaskar", "नमस्ते", "नमस्कार", " help ", "madad", "मदद")
TRACK = ("status", "track", "my report", "my complaint", "update on", "kya hua", "kab hoga", "स्थिति", "स्टेटस",
         "माझी तक्रार", "तक्रारीची", "मेरी शिकायत", "meri complaint", "meri report", "progress")
WHY = ("why", "kyun", "kyon", "क्यों", "priority", "urgent", "प्राधान्य", "प्राथमिकता")
WORK = ("anything done", "work done", "public work", "project", "kaam", "काम", "mplads", "kya kiya", "kuch kiya",
        "funded", "sanction")
HISTORY = ("before", "history", "pehle", "पहले", "आधी", "again", "recurring", "baar baar", "बार बार", "पुन्हा",
           "happened here")
CANCEL = ("cancel", "stop", "never mind", "nevermind", "rehne do", "रद्द", "रहने दो")

ADMIN_BRIEFING = ("attention", "today", "summary", "summarise", "summarize", "briefing", "priorities",
                  "what needs", "overview")
ADMIN_VERIFICATION = ("verification", "verify", "evidence queue", "review queue")
ADMIN_DEADLINE = ("sla", "deadline", "breach", "overdue", "due soon", "approaching")
ADMIN_RECURRING = ("recurr", "repeat", "reopen")
ADMIN_LIST = ("show", "list", "find", "search", "which")

# Category words for admin filters, and for one measured classifier blind
# spot: standing water on a road ("road pe paani jama hai") classifies as
# pothole_road at 0.91, but in PMC's taxonomy waterlogging is a drainage
# failure. The citizen still confirms the category before anything is sent.
WATERLOGGING = ("waterlog", "water logging", "paani jama", "pani jama", "paani bhar", "stagnant water",
                "पाणी साचल", "पानी जमा", "पानी भर", "जलभराव", "तुंबल", "tumbla", "flooded road")
CATEGORY_WORDS = {
    "drainage_sewage": ("drain", "sewage", "sewer", "gutter", "nala", "nallah", "chamber", "नाली", "गटार",
                        "ड्रेनेज") + WATERLOGGING,
    "pothole_road": ("pothole", "road", "gaddha", "gadda", "खड्डा", "गड्ढा", "सड़क", "रस्ता"),
    "water_supply": ("water supply", "no water", "pipeline", "leak", "tap", "पाणीपुरवठा", "पानी नहीं", "नळ"),
    "streetlight": ("streetlight", "street light", "lamp", "batti", "दिवा", "लाइट", "बत्ती"),
    "garbage_waste": ("garbage", "waste", "trash", "kachra", "कचरा", "dump"),
    "footpath": ("footpath", "sidewalk", "pavement", "फुटपाथ", "पदपथ"),
    "traffic_signage": ("traffic", "signal", "signage", "सिग्नल"),
}


_WATER = ("paani", "pani", "पाणी", "पानी", "water")
_STANDING = ("jama", "bhar", "साचल", "साचले", "जमा", "भर", "logged", "stagnant", "standing", "tumb", "तुंब", "collect")


def mentions_waterlogging(text: str) -> bool:
    """'paani jama', 'पाणी खूप साचलं' (words between), 'water standing'."""
    return _has(text, WATERLOGGING) or (_has(text, _WATER) and _has(text, _STANDING))


def mentions_high_priority(text: str) -> bool:
    return _has(text, ("critical", "high", "urgent", "serious"))


def category_from_words(text: str) -> Optional[str]:
    """Waterlogging first (it also mentions 'road'), then the first category
    whose words appear. None when nothing matches - never a guess."""
    if mentions_waterlogging(text):
        return "drainage_sewage"
    for category, words in CATEGORY_WORDS.items():
        if _has(text, words):
            return category
    return None


def valid_category(value: Optional[str]) -> Optional[str]:
    return value if value in CIVIC_CATEGORIES else None


_DURATION = re.compile(
    r"(since\s+(yesterday|last\s+\w+|\d+\s+\w+)|for\s+\d+\s+(days?|weeks?|months?)|kal\s+(raat\s+)?se|"
    r"\d+\s+(din|hafte|mahine)\s+se|कल\s+से|कल\s+रात\s+से|\d+\s+दिनों\s+से|काल\s+पासून|\d+\s+दिवसांपासून)",
    re.IGNORECASE)


def duration_phrase(text: str) -> Optional[str]:
    """The citizen's own words for how long ('since yesterday', 'kal raat se')."""
    m = _DURATION.search(text)
    return m.group(0) if m else None


def citizen_intent(text: str, has_issue_context: bool) -> str:
    if issue_ref(text) is not None:
        return "issue"
    if _has(text, CANCEL) and len(text.split()) <= 3:
        return "cancel"
    if _has(text, TRACK):
        return "track"
    if has_issue_context and _has(text, WORK):
        return "work"
    if has_issue_context and _has(text, HISTORY):
        return "history"
    if has_issue_context and _has(text, WHY):
        return "priority"
    if _has(text, GREETING) and len(text.split()) <= 4:
        return "greeting"
    return "complaint"


def admin_intent(text: str, has_issue_context: bool) -> str:
    if work_ref(text) is not None:
        return "work"
    if issue_ref(text) is not None:
        return "explain"
    if has_issue_context and _has(text, ("this case", "this issue", "summarize this", "summarise this", "why")):
        return "explain"
    if _has(text, ADMIN_DEADLINE):
        return "deadlines"
    if _has(text, ADMIN_VERIFICATION):
        return "verification"
    if has_issue_context and _has(text, WHY + ("explain", "evidence", "detail")):
        return "explain"
    if has_issue_context and _has(text, HISTORY):
        return "history"
    if _has(text, ADMIN_RECURRING):
        return "recurring"
    if _has(text, ADMIN_LIST) or category_from_words(text) or mentions_high_priority(text):
        # "Show me today's critical drainage issues" is a filtered list, not the briefing.
        return "list"
    if _has(text, ADMIN_BRIEFING):
        return "briefing"
    return "help"
