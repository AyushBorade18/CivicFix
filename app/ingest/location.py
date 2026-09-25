import csv
import re
from functools import lru_cache

GAZETTEER_CSV = "data/gazetteer/pune_gazetteer_osm.csv"
# Most specific wins when a text names several places ("Sutardara, Kothrud").
# Roads (span many wards) and ambiguous names are never used to place anything.
_GAZETTEER_SPECIFICITY = {"junction": 5, "neighbourhood": 4, "locality": 3, "quarter": 3,
                          "suburb": 2, "village": 1, "hamlet": 1}
_WORD_CHAR = r"[\wऀ-ॿ]"  # Devanagari vowel signs aren't \w, so \b fails inside Marathi words

# Landmark phrases that geocode to something, but never to the right place.
JUNK_LANDMARKS = {
    "survey no", "office at", "park", "shri", "pcmc", "post", "the village",
    "gram panchayat", "village", "taluka", "ward no", "ward number",
}

_WARD_PATTERN = re.compile(r"\bward\s*(?:no\.?|number|num\.?)?\s*[:\-]?\s*(\d{1,2})\b", re.I)

_LANDMARK_PATTERN = re.compile(
    r"(?:near|at|opposite|behind|adjoining|adj\.?)\s+"
    r"([A-Za-z0-9][A-Za-z0-9\.\-\'\s]{2,50}?)"
    r"(?=,|\.| taluka| tal\.| district| dist\.| ward|$)",
    re.I,
)
_LANDMARK_STOPWORDS = {"sub", "ward", "dist", "tal", "no", "office"}

# Words that mean the landmark phrase has run into the next clause rather
# than continuing the place name (only matters when the sentence has no
# punctuation to stop at, e.g. "near Pashan Lake causing accidents").
_CONTINUATION_STOPWORDS = {
    "causing", "again", "today", "please", "urgently", "reported", "since",
    "because", "after", "before", "which", "that", "and", "for", "the",
    "this", "every", "time", "times", "daily", "weekly", "currently",
    "recently", "now", "still", "here", "there", "also", "already",
    "in", "of", "on", "is", "are", "was", "were", "has", "have", "had",
}
_LEADING_DETERMINERS = {"the", "a", "an"}


def extract_ward_number(text: str, max_ward_id: int = 58) -> int | None:
    """Pulls an explicit ward number out of free text, e.g. "Ward no.20",
    "ward no 20", "Ward 9". Returns None if absent or out of range rather
    than guessing.
    """
    if not text:
        return None
    match = _WARD_PATTERN.search(text)
    if not match:
        return None
    n = int(match.group(1))
    if not (1 <= n <= max_ward_id):
        return None
    return n


def extract_landmark_phrase(text: str) -> str | None:
    """Pulls a coarse "near/at/opposite/behind X" landmark phrase out of free
    text, for use as a geocoding query. This is a stopgap regex, not the
    real NER + gazetteer pipeline (app/nlp/location.py, Lane B) - it exists
    only so MPLADS works ingestion has something better than geocoding a raw,
    ungrammatical sentence (which reliably returns zero Nominatim results).
    """
    if not text:
        return None
    match = _LANDMARK_PATTERN.search(text)
    if not match:
        return None
    raw = match.group(1).strip().strip(".")

    remaining = raw.split()
    while remaining and remaining[0].lower() in _LEADING_DETERMINERS:
        remaining.pop(0)

    words = []
    for word in remaining:
        if word.lower().strip(".,") in _CONTINUATION_STOPWORDS:
            break
        words.append(word)
    phrase = " ".join(words)

    if len(phrase) < 4 or phrase.lower() in _LANDMARK_STOPWORDS:
        return None
    return phrase


@lru_cache(maxsize=1)
def _gazetteer_places() -> list[tuple[re.Pattern, dict]]:
    places = []
    with open(GAZETTEER_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["kind"] not in _GAZETTEER_SPECIFICITY:
                continue
            names = {row["name_en"], row["romanized_variants"], row["name_marathi"]}
            for name in names:
                if len(name) >= 4:
                    pattern = re.compile(rf"(?<!{_WORD_CHAR}){re.escape(name)}(?!{_WORD_CHAR})", re.I)
                    places.append((pattern, row))
    return places


def find_gazetteer_place(text: str) -> dict | None:
    """Returns the most specific Pune gazetteer place named in the text (a
    data/gazetteer/pune_gazetteer_osm.csv row), or None. English or Marathi
    names. A place's point is its OSM centre, so callers must treat it as
    locality-level evidence, never as a precise location.
    """
    if not text:
        return None
    hits = [row for pattern, row in _gazetteer_places() if pattern.search(text)]
    if not hits:
        return None
    return max(hits, key=lambda r: (_GAZETTEER_SPECIFICITY[r["kind"]], len(r["name_en"])))
