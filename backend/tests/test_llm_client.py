from __future__ import annotations

import httpx
import pytest

from app.llm.client import (
    FakeProvider, LLMClient, LLMUnavailable, ModelChain, RateLimited, RateLimiter, TransientError,
)
from app.llm.gemini import GeminiProvider
from app.privacy_gate.gate import PrivacyGate, explanation_payload, slot_extraction_payload


@pytest.fixture(scope="module")
def gate(lex):
    return PrivacyGate(lex)


def make_client(lex, provider, models=("lite", "flash"), enabled=True, limiters=None, sleeps=None):
    chain = ModelChain(provider, list(models), limiters or {}, sleep=(sleeps.append if sleeps is not None else lambda s: None))
    return LLMClient(chain, lex.allowed_tokens(), enabled)


def test_gated_payload_is_sent(lex, gate):
    fake = FakeProvider(lambda m, p: {"sites": 2})
    client = make_client(lex, fake)
    payload = slot_extraction_payload(gate.apply("do branch hain"), {}, ["sites"], "hinglish")
    assert client.send("sys", payload, {}) == {"sites": 2}
    assert fake.calls[0][0] == "lite"


def test_client_rejects_raw_text_even_if_gate_is_bypassed(lex):
    client = make_client(lex, FakeProvider())
    raw = {"task": "extract_slots", "language": "en", "message": "I am Rakesh Malhotra",
           "known": {k: None for k in ("segment", "city_tier", "employees_band", "sites_band", "has_gstin")},
           "missing": []}
    with pytest.raises(ValueError, match="allowlist"):
        client.send("sys", raw, {})


def test_client_rejects_unexpected_payload_shapes(lex, gate):
    client = make_client(lex, FakeProvider())
    good = slot_extraction_payload(gate.apply("GST hai"), {"city": "Pune"}, [], "en")
    with pytest.raises(ValueError):
        client.send("sys", {**good, "city": "Pune"}, {})
    with pytest.raises(ValueError):
        client.send("sys", {**good, "known": {**good["known"], "city": "Pune"}}, {})


def test_explanation_payload_is_allowed(lex):
    client = make_client(lex, FakeProvider(lambda m, p: {"P02:X": "ok"}))
    assert client.send("sys", explanation_payload([("X", "P02")], {}, "en"), {}) == {"P02:X": "ok"}


def test_disabled_client_raises_unavailable(lex, gate):
    client = LLMClient(None, lex.allowed_tokens(), enabled=True)
    with pytest.raises(LLMUnavailable):
        client.send("sys", slot_extraction_payload(gate.apply("GST hai"), {}, [], "en"), {})


def test_429_moves_to_next_model_without_retry(lex, gate):
    calls = []

    class P:
        def generate(self, model, system, payload, schema):
            calls.append(model)
            if model == "lite":
                raise RateLimited()
            return {"ok": True}

    client = make_client(lex, P())
    assert client.send("s", slot_extraction_payload(gate.apply("GST hai"), {}, [], "en"), {}) == {"ok": True}
    assert calls == ["lite", "flash"]


def test_transient_error_retries_once_then_moves_on(lex, gate):
    calls, sleeps = [], []

    class P:
        def generate(self, model, system, payload, schema):
            calls.append(model)
            raise TransientError("503")

    client = make_client(lex, P(), sleeps=sleeps)
    with pytest.raises(LLMUnavailable):
        client.send("s", slot_extraction_payload(gate.apply("GST hai"), {}, [], "en"), {})
    assert calls == ["lite", "lite", "flash", "flash"] and sleeps == [1.0, 1.0]


def test_rate_limiter_minute_and_day_budgets():
    t = [0.0]
    lim = RateLimiter(rpm=2, rpd=3, clock=lambda: t[0])
    assert lim.try_acquire() and lim.try_acquire() and not lim.try_acquire()
    t[0] = 61
    assert lim.try_acquire() and not lim.try_acquire()  # day budget of 3 used
    t[0] = 86_500
    assert lim.try_acquire()


def test_limited_model_is_skipped(lex, gate):
    fake = FakeProvider(lambda m, p: {"m": m})
    lim = RateLimiter(rpm=0, rpd=0)
    client = make_client(lex, fake, limiters={"lite": lim})
    assert client.send("s", slot_extraction_payload(gate.apply("GST hai"), {}, [], "en"), {}) == {"m": "flash"}


def _gemini(handler):
    return GeminiProvider("test-key", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_gemini_provider_parses_json_and_keeps_key_out_of_url():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["key"] = str(request.url), request.headers.get("x-goog-api-key")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"sites": 2}'}]}}]})

    assert _gemini(handler).generate("gemini-x", "sys", {"task": "explain"}, {}) == {"sites": 2}
    assert "test-key" not in seen["url"] and seen["key"] == "test-key"


@pytest.mark.parametrize("status, exc", [(429, RateLimited), (503, TransientError), (400, RateLimited)])
def test_gemini_provider_maps_errors(status, exc):
    with pytest.raises(exc):
        _gemini(lambda r: httpx.Response(status)).generate("m", "s", {}, {})
