from training.synthetic.assemble import detect_script, has_pii, script_problem, shingle_similarity


def test_detects_script():
    assert detect_script("Baner madhe pani yet nahi") == "latin"
    assert detect_script("बाणेर मध्ये पाणी येत नाही") == "devanagari"
    assert detect_script("बाणेर मध्ये water pressure कमी आहे") == "mixed"


def test_script_must_match_language():
    assert script_problem("romanized_marathi", "latin", "पाणी नाही") is not None
    assert script_problem("marathi", "devanagari", "पाणी येत नाही") is None
    assert script_problem("marathi", "devanagari", "पाणी येत नाही since morning") is not None
    assert script_problem("hinglish", "mixed", "सड़क पे bahut gaddhe hain") is None
    assert script_problem("hinglish", "latin", "सड़क पे bahut gaddhe hain") is not None


def test_flags_pii():
    assert has_pii("call me on 9876543210")
    assert has_pii("mail ravi@gmail.com")
    assert has_pii("Mr. Sharma said the drain is blocked")
    assert not has_pii("drain near lane 5 blocked for 3 days")


def test_near_duplicate_similarity():
    a = "Kothrud madhe teen divas kachra uchalla nahi"
    assert shingle_similarity(a, a + ".") > 0.9
    assert shingle_similarity(a, "Signal at Swargate chowk is not working since morning") < 0.2
