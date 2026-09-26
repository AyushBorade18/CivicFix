import pytest

from app.nlp.severity import severity, severity_keywords


def test_open_manhole_is_critical_regardless_of_mild_wording():
    assert severity("There is an open manhole near the school gate", "drainage_sewage") == "critical"


def test_category_prior_wins_when_text_has_no_severity_keywords():
    # drainage_sewage's prior is critical even with completely neutral text
    assert severity("Drainage issue reported today", "drainage_sewage") == "critical"


def test_text_severity_can_escalate_above_category_prior():
    # streetlight's prior is cosmetic, but "accident" text should escalate
    assert severity("Streetlight out and a scooter accident happened here last night", "streetlight") == "critical"


def test_low_severity_category_with_mild_text_stays_low():
    assert severity("Streetlight flickering occasionally", "streetlight") == "cosmetic"


def test_moderate_text_on_low_prior_category():
    assert severity("Footpath tiles are broken and uneven", "footpath") == "moderate"


def test_unknown_category_defaults_to_cosmetic_prior():
    assert severity("Some minor issue", "other") == "cosmetic"


def test_empty_text_falls_back_to_category_prior():
    assert severity("", "water_supply") == "moderate"


# --- multilingual parity -----------------------------------------------------
# Intake accepts Marathi/Hindi/romanized text, but the keyword list was
# English-only, so an identical hazard scored a whole band lower in Marathi.
# Severity carries the heaviest priority weight (0.35), so that gap pushed
# non-English complaints down the queue.

MATCHED_HAZARDS = [
    # (category, English, Devanagari, romanized) - all three must agree
    ("streetlight", "exposed wires here, electrocution risk",
     "येथे उघड्या तारा आहेत, विजेचा धक्का बसू शकतो",
     "ithe ughdya tara aahet, current cha dhakka basu shakto"),
    ("pothole_road", "a two wheeler accident happened here, rider injured",
     "येथे दुचाकी अपघात झाला, चालक जखमी झाला",
     "ithe duchaki apghat zala, chalak jakhmi zala"),
    ("footpath", "the slab collapsed and a child fell into the gap",
     "स्लॅब कोसळला आणि एक मूल आत पडले",
     "slab kosalla ani ek mul aat padle"),
    ("water_supply", "contaminated water is coming from the tap",
     "नळाला दूषित पाणी येत आहे",
     "nalala dushit pani yet aahe"),
    ("garbage_waste", "the garbage caught fire near the houses",
     "घरांजवळ कचऱ्याला आग लागली",
     "gharanjaval kachryala aag lagli"),
]


@pytest.mark.parametrize("category,english,devanagari,romanized", MATCHED_HAZARDS)
def test_same_hazard_scores_the_same_band_in_every_script(category, english, devanagari, romanized):
    expected = severity(english, category)
    assert expected == "critical", "test case should describe a critical hazard"
    assert severity(devanagari, category) == expected
    assert severity(romanized, category) == expected


def test_moderate_marathi_text_escalates_a_cosmetic_category():
    assert severity("फुटपाथवरील फरशा तुटल्या आहेत", "footpath") == "moderate"


def test_moderate_hindi_text_escalates_a_cosmetic_category():
    assert severity("फुटपाथ की टाइलें टूट गई हैं", "footpath") == "moderate"


def test_mild_marathi_text_does_not_escalate():
    assert severity("पथदिवा अधूनमधून लुकलुकतो", "streetlight") == "cosmetic"


def test_keywords_cover_every_band_and_language_we_accept():
    keywords = severity_keywords()
    assert set(keywords) == {"critical", "moderate"}
    joined = " ".join(w for words in keywords.values() for w in words)
    assert any("ऀ" <= ch <= "ॿ" for ch in joined), "no Devanagari keywords loaded"
    for band in ("critical", "moderate"):
        assert len(keywords[band]) >= 20, f"{band} list looks too thin to be multilingual"
