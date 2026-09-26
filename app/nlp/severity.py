import csv
from functools import lru_cache

_BAND_ORDER = ("cosmetic", "moderate", "critical")

# Published category priors, per ARCHITECTURE.md 5.4: some categories are
# dangerous regardless of how mildly they're worded (an open manhole or
# sewage near water is never "cosmetic").
CATEGORY_SEVERITY_PRIOR = {
    "pothole_road": "moderate",
    "drainage_sewage": "critical",
    "water_supply": "moderate",
    "streetlight": "cosmetic",
    "garbage_waste": "moderate",
    "footpath": "cosmetic",
    "traffic_signage": "moderate",
    "other": "cosmetic",
}

SEVERITY_KEYWORDS_CSV = "data/labelling/severity_keywords.csv"


@lru_cache(maxsize=1)
def severity_keywords() -> dict[str, tuple[str, ...]]:
    """Keywords per band, from SEVERITY_KEYWORDS_CSV.

    They live in a CSV rather than in this file because intake accepts
    Marathi, Hindi and romanized text: the list has to carry a language, a
    script and an example sentence per entry so a native speaker can review
    it (that review is a data edit, not a code change). Keeping a second
    copy here as a constant would just let the two drift.
    """
    bands: dict[str, list[str]] = {"critical": [], "moderate": []}
    with open(SEVERITY_KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            band = row["severity_band"].strip()
            word = row["word_or_phrase"].strip().lower()
            # One phrase can be valid in two languages (Marathi and Hindi
            # share खराब), which is two review rows but one matcher entry.
            if word and band in bands and word not in bands[band]:
                bands[band].append(word)
    return {band: tuple(words) for band, words in bands.items()}


def _text_severity(text: str) -> str:
    lowered = (text or "").lower()
    keywords = severity_keywords()
    for band in ("critical", "moderate"):
        if any(keyword in lowered for keyword in keywords[band]):
            return band
    return "cosmetic"


def severity(text: str, category: str) -> str:
    """severity = max(category_prior, text_severity). Deterministic, no
    model - per ARCHITECTURE.md 5.4, photos are evidence only, never a
    severity signal.
    """
    prior = CATEGORY_SEVERITY_PRIOR.get(category, "cosmetic")
    text_band = _text_severity(text)
    return max(prior, text_band, key=_BAND_ORDER.index)
