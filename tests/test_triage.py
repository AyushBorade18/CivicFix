"""LLM triage fallback: every failure must degrade to 'review', never 'spam'.
No test here calls the real API - the client is replaced with a fake."""
from types import SimpleNamespace

from google.genai import errors, types

from app.nlp import triage as triage_mod
from app.nlp.triage import Triage, triage


def _fake_client(monkeypatch, generate):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(triage_mod, "_client", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))


def _response(parsed, finish_reason=types.FinishReason.STOP):
    return SimpleNamespace(parsed=parsed, candidates=[SimpleNamespace(finish_reason=finish_reason)])


def test_no_api_key_sends_to_review_and_says_why(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = triage("asdf qwer buy followers now", None)
    assert result["verdict"] == "review"
    assert "GEMINI_API_KEY" in result["reason"]
    assert result["model"] is None


def test_free_tier_quota_exhausted_sends_to_review_not_spam(monkeypatch):
    def generate(**kwargs):
        raise errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    _fake_client(monkeypatch, generate)
    result = triage("some complaint", None)
    assert result["verdict"] == "review"
    assert "ClientError" in result["reason"]


def test_network_failure_sends_to_review(monkeypatch):
    def generate(**kwargs):
        raise ConnectionError("no route to host")
    _fake_client(monkeypatch, generate)
    assert triage("some complaint", None)["verdict"] == "review"


def test_truncated_or_blocked_output_sends_to_review(monkeypatch):
    _fake_client(monkeypatch, lambda **kw: _response(None, finish_reason=types.FinishReason.MAX_TOKENS))
    result = triage("some complaint", None)
    assert result["verdict"] == "review"
    assert "MAX_TOKENS" in result["reason"]

    _fake_client(monkeypatch, lambda **kw: SimpleNamespace(parsed=None, candidates=[]))  # prompt blocked
    assert triage("some complaint", None)["verdict"] == "review"


def test_spam_verdict_passes_through_with_provenance(monkeypatch):
    seen = {}

    def generate(**kwargs):
        seen.update(kwargs)
        return _response(Triage(verdict="spam", category="other", reason="Promotional text, no civic issue."))
    _fake_client(monkeypatch, generate)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    result = triage("Earn 50000 per week from home, WhatsApp now", None)
    assert result == {
        "verdict": "spam", "category": "other", "reason": "Promotional text, no civic issue.",
        "model": triage_mod.DEFAULT_MODEL, "prompt_version": triage_mod.PROMPT_VERSION,
    }
    assert seen["model"] == triage_mod.DEFAULT_MODEL
    assert seen["config"].response_schema is Triage


def test_original_and_translation_are_both_sent(monkeypatch):
    seen = {}

    def generate(**kwargs):
        seen.update(kwargs)
        return _response(Triage(verdict="accept", category="drainage_sewage", reason="Blocked gutter."))
    _fake_client(monkeypatch, generate)

    result = triage("गटार तुंबले आहे", "The gutter is blocked")
    assert result["verdict"] == "accept" and result["category"] == "drainage_sewage"
    assert "गटार तुंबले आहे" in seen["contents"] and "The gutter is blocked" in seen["contents"]


def test_client_is_kept_alive_between_calls(monkeypatch):
    """A throwaway genai.Client is garbage-collected before its request goes
    out, closing its connection - every live call then failed with
    'client has been closed'. The client must be reused."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert triage_mod._client() is triage_mod._client()
