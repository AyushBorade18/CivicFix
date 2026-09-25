from app.nlp.translate import translate_to_english


def test_unsupported_language_returns_none():
    assert translate_to_english("bonjour le monde", "fr") is None


def test_english_source_not_in_map_returns_none():
    assert translate_to_english("hello", "en") is None


def _fake_urlopen(payload=None, error=None):
    import io
    import json

    def urlopen(url, timeout=None):
        assert timeout is not None, "a live report must never wait on the network without a timeout"
        if error:
            raise error
        return io.BytesIO(json.dumps(payload).encode())
    return urlopen


def test_translation_failure_degrades_to_none(monkeypatch):
    import app.nlp.translate as translate_module

    translate_to_english.cache_clear()
    monkeypatch.setattr(translate_module.urllib.request, "urlopen",
                        _fake_urlopen(error=RuntimeError("service unavailable")))
    assert translate_to_english("कुछ भी", "hi") is None


def test_network_timeout_degrades_to_none(monkeypatch):
    import socket

    import app.nlp.translate as translate_module

    translate_to_english.cache_clear()
    monkeypatch.setattr(translate_module.urllib.request, "urlopen",
                        _fake_urlopen(error=socket.timeout("timed out")))
    assert translate_to_english("रस्त्यावर खड्डा", "mr") is None


def test_quota_warning_is_never_returned_as_a_translation(monkeypatch):
    import app.nlp.translate as translate_module

    translate_to_english.cache_clear()
    payload = {"responseStatus": 429, "responseData": {
        "translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY."}}
    monkeypatch.setattr(translate_module.urllib.request, "urlopen", _fake_urlopen(payload))
    assert translate_to_english("सड़क टूटी है", "hi") is None


def test_successful_response_returns_translation(monkeypatch):
    import app.nlp.translate as translate_module

    translate_to_english.cache_clear()
    payload = {"responseStatus": 200, "responseData": {"translatedText": "Big pothole on the road"}}
    monkeypatch.setattr(translate_module.urllib.request, "urlopen", _fake_urlopen(payload))
    assert translate_to_english("सड़क पर गड्ढा", "hi") == "Big pothole on the road"


def test_real_hindi_translation_produces_english_text():
    # A real network call to the free MyMemory service - skip rather than
    # fail the whole suite if it's unreachable from this environment.
    import pytest

    result = translate_to_english("सड़क पर बहुत बड़ा गड्ढा है", "hi")
    if result is None:
        pytest.skip("MyMemory translation service unreachable in this environment")
    assert isinstance(result, str) and len(result) > 0
    assert "hole" in result.lower() or "pit" in result.lower() or "pothole" in result.lower()
