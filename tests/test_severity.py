import pytest

from app.nlp.severity import severity, severity_keywords


def test_open_manhole_is_critical_regardless_of_mild_wording():
    assert severity("There is an open manhole near the school gate", "drainage_sewage") == "critical"


def test_category_prior_wins_when_text_has_no_severity_keywords():
    # The prior is still the floor for neutral text - it just isn't "critical"
    # for drainage any more (see CATEGORY_SEVERITY_PRIOR). A streetlight report
    # with no hazard wording stays at its cosmetic prior; drainage sits at
    # moderate rather than dropping to cosmetic.
    assert severity("Drainage issue reported today", "drainage_sewage") == "moderate"
    assert severity("Streetlight issue reported today", "streetlight") == "cosmetic"


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


# --- hazard classes the gold-set evaluation found missing ---------------------
# Each of these is a real complaint from data/labelling/lo2_gold_complaints.csv
# that humans called critical and the keyword list scored lower. See
# scripts/eval/gold_eval.py; the gold_id is named so the case is traceable.

CRITICAL_HAZARDS = [
    ("G033", "streetlight", "live wire on footpath near viman nagar symbiosys"),
    ("G022", "streetlight", "lohegaon sai ganesh park light pole is broken wires hanging"),
    ("G017", "garbage_waste", "NCC HQ SB road pe kachra jala rahe hai. Dhua hi dhua hai."),
    ("G018", "water_supply", "Sutardara main road tap water is muddy and smells like sewage"),
    ("G003", "pothole_road", "D mart baner ke samne bohot bada pothole hai 2 log gir gaye kal"),
    ("G055", "pothole_road", "Deep pothole caused a two-wheeler to skid at night, rider got hurt"),
    ("G061", "pothole_road", "Raat ke samay MNGL gas line ka khadda khula aur bina kisi marking ke chhod diya"),
]


@pytest.mark.parametrize("gold_id,category,text", CRITICAL_HAZARDS)
def test_real_hazards_from_the_gold_set_score_critical(gold_id, category, text):
    assert severity(text, category) == "critical", f"{gold_id} is a hazard, not a lesser band"


DEVANAGARI_HAZARDS = [
    ("streetlight", "फुटपाथवर जिवंत तार पडली आहे"),
    ("streetlight", "खांबावरून तारा लटकत आहेत"),
    ("garbage_waste", "कचरा जाळत आहेत, सगळीकडे धूर"),
    ("pothole_road", "रस्त्यावर उघडा खड्डा आहे"),
]


@pytest.mark.parametrize("category,text", DEVANAGARI_HAZARDS)
def test_the_same_hazard_classes_work_in_devanagari(category, text):
    assert severity(text, category) == "critical"


def test_a_tree_across_a_footpath_is_moderate_not_critical():
    # Gold labels both tree cases (G020, G051) moderate: it blocks access
    # rather than threatening a life. Encoded so nobody "upgrades" it later.
    assert severity("fallen tree blocking the main gate society", "other") == "moderate"


def test_a_dark_street_is_moderate():
    assert severity("Sai ganesh park street light is off very dark at night", "streetlight") == "moderate"


def test_stray_dogs_and_debris_are_moderate():
    assert severity("stray dogs chasing morning walkers near a park entrance", "other") == "moderate"
    assert severity("construction ka malba phenka gaya hai", "other") == "moderate"


def test_a_plain_drainage_report_is_no_longer_critical_by_default():
    # The prior used to hardcode drainage_sewage critical, which made every
    # routine gutter complaint top-band (11 of 33 gold misses were this).
    assert severity("Drainage issue reported today", "drainage_sewage") == "moderate"


def test_drainage_still_escalates_on_real_hazard_wording():
    assert severity("Sewage near the drinking water line", "drainage_sewage") == "critical"
    assert severity("गटारात सांडपाणी तुंबले आणि दूषित पाणी येत आहे", "drainage_sewage") == "critical"
