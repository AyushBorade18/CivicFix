"""Real translation, not a stub - lets a non-English report actually be
classified/severity-scored/geocoded by the existing English-only pipeline,
instead of only being flagged (see app/nlp/language.py). Uses MyMemory, a
free, no-API-key translation service, chosen after Google's free endpoint
returned TooManyRequests immediately in this environment - MyMemory tested
reliably for Hindi and Marathi, the languages this civic system most needs.

Called directly (not via deep-translator): that library sends the request
with no timeout, so a flaky network would hang a live report submission
forever, and it passes MyMemory's quota warning through as if it were the
translation.

Only languages this system explicitly claims to support (matching
LANGUAGE_LABELS in web/src/components/Badges.tsx) are attempted - an
unmapped code degrades to None (no translation) rather than guessing a
MyMemory locale code that might not exist.
"""
import json
import urllib.parse
import urllib.request
from functools import lru_cache

MYMEMORY_URL = "https://api.mymemory.translated.net/get"
TIMEOUT_SECONDS = 4  # a live report must never wait longer on venue wifi

# langdetect ISO 639-1 code -> MyMemory locale code
_MYMEMORY_SOURCE = {
    "hi": "hi-IN", "mr": "mr-IN", "ur": "ur-PK", "ta": "ta-IN", "te": "te-IN",
    "bn": "bn-IN", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN", "pa": "pa-IN",
}
_MYMEMORY_TARGET = "en-GB"
# MyMemory reports quota/length problems inside translatedText, not as errors.
_SERVICE_WARNINGS = ("MYMEMORY WARNING", "QUERY LENGTH LIMIT", "INVALID LANGUAGE PAIR")


@lru_cache(maxsize=512)
def translate_to_english(text: str, language: str) -> str | None:
    """Returns an English translation, or None if the language isn't one we
    translate or the call fails (network, timeout, quota, bad response) -
    callers must fall back to running the pipeline on the original text,
    never crash, per the graceful-degradation rule. Cached so a repeated
    demo submission doesn't spend the free daily quota again."""
    source = _MYMEMORY_SOURCE.get(language)
    if source is None:
        return None
    params = urllib.parse.urlencode({"q": text, "langpair": f"{source}|{_MYMEMORY_TARGET}"})
    try:
        with urllib.request.urlopen(f"{MYMEMORY_URL}?{params}", timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read())
    except Exception:
        return None
    if str(data.get("responseStatus")) != "200":
        return None
    translation = ((data.get("responseData") or {}).get("translatedText") or "").strip()
    if not translation or translation.upper().startswith(_SERVICE_WARNINGS):
        return None
    return translation
