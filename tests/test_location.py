from app.ingest.location import extract_landmark_phrase, extract_ward_number


def test_ward_no_dot_number_no_space():
    assert extract_ward_number("...at Shivkirti Ghorpadi ward no.20") == 20


def test_ward_no_with_space():
    assert extract_ward_number("Create Waiting Room at Sub.Div.No.3 Office. Ward no 20") == 20


def test_ward_number_no_qualifier():
    assert extract_ward_number("At Ward 9 Establishment of a bus stop at D-Mart, Baner.") == 9


def test_road_concreting_ward_dot():
    assert extract_ward_number("Road Concreting at Ward No.11, Sutardara Kothrud.") == 11


def test_does_not_false_positive_on_sub_division_number():
    assert extract_ward_number("Paud Police Station Computer Dell Inspiron - 4, Sub.Div.No.3") is None


def test_out_of_range_ward_number_returns_none():
    assert extract_ward_number("Ward no 200 renovation") is None


def test_no_ward_mention_returns_none():
    assert extract_ward_number("Construction of a public hall at Mulashi Khurd") is None


def test_empty_text_returns_none():
    assert extract_ward_number("") is None
    assert extract_ward_number(None) is None


def test_extracts_landmark_after_near():
    assert extract_landmark_phrase("Installation Of Exercise Equipment Near Pashan lake") == "Pashan lake"


def test_extracts_landmark_after_at_with_comma():
    assert extract_landmark_phrase("Construction of a public hall at Mulashi Khurd, Pune District") == "Mulashi Khurd"


def test_extracts_landmark_stops_before_ward_mention():
    assert extract_landmark_phrase("Establishment of a bus stop at Ashish Garden, Kothrud Up") == "Ashish Garden"


def test_rejects_short_office_jargon_stopword():
    assert extract_landmark_phrase("Create Waiting Room at Sub.Div.No.3 Office.") is None


def test_no_landmark_marker_returns_none():
    assert extract_landmark_phrase("Sarve no 15 83 462 496 663 distict Junnar Pune") is None


def test_empty_text_returns_none_for_landmark():
    assert extract_landmark_phrase("") is None
    assert extract_landmark_phrase(None) is None


def test_stops_at_continuation_word_when_no_punctuation():
    # Regression: without punctuation to stop at, the old regex swallowed
    # the rest of the sentence ("Pashan Lake causing accidents").
    assert extract_landmark_phrase("Pothole near Pashan Lake causing accidents") == "Pashan Lake"


def test_skips_leading_determiner_instead_of_returning_none():
    # Regression: a leading "the" used to be treated as an instant stopword
    # hit, discarding the whole phrase instead of just skipping "the".
    assert extract_landmark_phrase("Toilet built at the water tank at NCC Headquarters") == "water tank at NCC Headquarters"


def test_strips_trailing_preposition():
    assert extract_landmark_phrase("Footpath work near Dattawadi in the Pune Lok Sabha constituency") == "Dattawadi"


def test_stops_at_copula_not_captured_into_phrase():
    # Regression: found while generating synthetic complaints - templates
    # like "{landmark} is broken" produced garbage geocode queries like
    # "Airport Road is broken" because "is"/"are" weren't stop words.
    assert extract_landmark_phrase("No proper footpath near Airport Road is broken and unusable") == "Airport Road"
    assert extract_landmark_phrase("Footpath tiles near Dasara Chowk are uneven and cracked") == "Dasara Chowk"


def test_gazetteer_prefers_most_specific_place_and_reads_marathi():
    from app.ingest.location import find_gazetteer_place
    assert find_gazetteer_place("Construction of toilet at Kasba Peth, Pune")["name_en"] == "Kasba Peth"
    assert find_gazetteer_place("कसबा पेठ येथे कचरा")["name_en"] == "Kasba Peth"
    assert find_gazetteer_place("Road work near nowhere-in-particular xyz") is None


def test_gazetteer_never_places_by_road_name():
    from app.ingest.location import find_gazetteer_place
    assert find_gazetteer_place("Construction Of Road Towards DP Road") is None


def test_pcmc_and_rural_text_is_flagged_outside_pmc():
    from app.ingest.location import outside_pmc_text
    assert outside_pmc_text("Construction of roads At. Pashan Mala towords Shivraj Residancy Society Tq. Shirur")
    assert outside_pmc_text("Fixing A Solar High Mast Lamp In Dongarwadi At Chabsar Grampanchayt Tal Maval")
    assert outside_pmc_text("Construct road At Thergaon PCmc Area")
    assert not outside_pmc_text("Laying Of Drainage Line at Ward No.11, Kishkindhanagar Kothrud")


def test_route_descriptions_are_not_geocodable_places():
    from app.ingest.location import is_route_phrase
    assert is_route_phrase("Forest to Pilanewasti road")
    assert not is_route_phrase("Pashan Lake")
