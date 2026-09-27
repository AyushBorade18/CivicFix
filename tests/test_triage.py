"""LLM triage fallback: every failure must degrade to 'review', never 'spam'.
No test here calls the real API - the client is replaced with a fake."""
from types import SimpleNamespace

import anthropic
import httpx2

from app.nlp import triage as triage_mod
from app.nlp.triage import Triage, triage


def _fake_client(monkeypatch, parse):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(triage_mod, "_client", lambda: SimpleNamespace(messages=SimpleNamespace(parse=parse)))


def _response(parsed, stop_reason="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)


def test_no_api_key_sends_to_review_and_says_why(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = triage("asdf qwer buy followers now", None)
    assert result["verdict"] == "review"
    assert "ANTHROPIC_API_KEY" in result["reason"]
    assert result["model"] is None


def test_api_error_sends_to_review_not_spam(monkeypatch):
    def parse(**kwargs):
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    _fake_client(monkeypatch, parse)
    result = triage("some complaint", None)
    assert result["verdict"] == "review"
    assert "APIConnectionError" in result["reason"]


def test_truncated_or_refused_output_sends_to_review(monkeypatch):
    _fake_client(monkeypatch, lambda **kw: _response(None, stop_reason="max_tokens"))
    result = triage("some complaint", None)
    assert result["verdict"] == "review"
    assert "max_tokens" in result["reason"]


def test_spam_verdict_passes_through_with_provenance(monkeypatch):
    seen = {}

    def parse(**kwargs):
        seen.update(kwargs)
        return _response(Triage(verdict="spam", category="other", reason="Promotional text, no civic issue."))
    _fake_client(monkeypatch, parse)

    result = triage("Earn 50000 per week from home, WhatsApp now", None)
    assert result == {
        "verdict": "spam", "category": "other", "reason": "Promotional text, no civic issue.",
        "model": triage_mod.MODEL, "prompt_version": triage_mod.PROMPT_VERSION,
    }
    assert seen["model"] == "claude-haiku-4-5"


def test_original_and_translation_are_both_sent(monkeypatch):
    seen = {}

    def parse(**kwargs):
        seen.update(kwargs)
        return _response(Triage(verdict="accept", category="drainage_sewage", reason="Blocked gutter."))
    _fake_client(monkeypatch, parse)

    result = triage("गटार तुंबले आहे", "The gutter is blocked")
    assert result["verdict"] == "accept" and result["category"] == "drainage_sewage"
    content = seen["messages"][0]["content"]
    assert "गटार तुंबले आहे" in content and "The gutter is blocked" in content
