"""LLM access, behind the privacy gate (DECISIONS.md D6, D6a; POLICIES.md §5).

- ``LLMClient.send`` accepts only the two payload shapes built in
  app.privacy_gate.gate, and re-checks every token of the message against the
  gate's allowlist before anything leaves the process (defence in depth).
- The client is disabled unless the red-team self-test passed at start-up
  (POLICIES.md §15 stop condition), an API key is set, and the advisor isn't
  in scripted mode.
- ``ModelChain``: on 429 move to the next model; on 5xx or timeout retry once
  after 1 s, then move on; if every model fails, raise LLMUnavailable and
  the advisor answers from its scripted path.
- ``RateLimiter``: per-model requests-per-minute and per-day budgets, kept in
  this (single) server process.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.advisor.lexicon import tokenize
from app.privacy_gate.gate import MASK

ALLOWED_PAYLOAD_KEYS = {
    "extract_slots": {"task", "language", "message", "known", "missing"},
    "explain": {"task", "language", "reasons", "known"},
}
KNOWN_KEYS = {"segment", "city_tier", "employees_band", "sites_band", "has_gstin"}


class LLMUnavailable(RuntimeError):
    """No model answered; the caller must use the scripted path."""


class RateLimited(Exception):
    pass


class TransientError(Exception):
    pass


class Provider(Protocol):
    def generate(self, model: str, system: str, payload: dict, schema: dict) -> dict: ...


@dataclass
class RateLimiter:
    rpm: int
    rpd: int
    clock: Callable[[], float] = time.monotonic
    _minute: deque = field(default_factory=deque)
    _day_count: int = 0
    _day_start: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def try_acquire(self) -> bool:
        with self._lock:
            now = self.clock()
            if self._day_start is None or now - self._day_start >= 86_400:
                self._day_start, self._day_count = now, 0
            while self._minute and now - self._minute[0] >= 60:
                self._minute.popleft()
            if len(self._minute) >= self.rpm or self._day_count >= self.rpd:
                return False
            self._minute.append(now)
            self._day_count += 1
            return True


class ModelChain:
    def __init__(self, provider: Provider, models: list[str], limiters: dict[str, RateLimiter],
                 sleep: Callable[[float], None] = time.sleep):
        self.provider, self.models, self.limiters, self.sleep = provider, models, limiters, sleep

    def generate(self, system: str, payload: dict, schema: dict) -> tuple[dict, str]:
        for model in self.models:
            limiter = self.limiters.get(model)
            if limiter and not limiter.try_acquire():
                continue
            for attempt in (1, 2):
                try:
                    return self.provider.generate(model, system, payload, schema), model
                except RateLimited:
                    break                      # no retry on 429; next model
                except TransientError:
                    if attempt == 1:
                        self.sleep(1.0)
                        continue
                    break
        raise LLMUnavailable("no model answered")


class LLMClient:
    def __init__(self, chain: ModelChain | None, allowed_tokens: set[str], enabled: bool,
                 disabled_reason: str = ""):
        self.chain = chain
        self._allowed = allowed_tokens
        self.enabled = enabled and chain is not None
        self.disabled_reason = disabled_reason if not self.enabled else ""
        self.sent: list[str] = []  # outbound bodies, kept for tests and the dev report only

    def _check(self, payload: dict) -> None:
        task = payload.get("task")
        if task not in ALLOWED_PAYLOAD_KEYS or set(payload) != ALLOWED_PAYLOAD_KEYS[task]:
            raise ValueError("payload shape not allowed")
        if set(payload["known"]) != KNOWN_KEYS:
            raise ValueError("known-slot keys not allowed")
        if task == "extract_slots":
            for tok in payload["message"].split():
                if tok == MASK:
                    continue
                for part in tokenize(tok):
                    if part not in self._allowed and not (part.isdigit() and len(part) <= 4):
                        raise ValueError("message contains a token outside the allowlist")
        else:
            for r in payload["reasons"]:
                if set(r) != {"code", "product_id"}:
                    raise ValueError("reason entry shape not allowed")

    def send(self, system: str, payload: dict, schema: dict) -> dict:
        if not self.enabled:
            raise LLMUnavailable(self.disabled_reason or "LLM disabled")
        self._check(payload)
        body = json.dumps(payload, ensure_ascii=False)
        self.sent.append(body)
        result, _model = self.chain.generate(system, payload, schema)
        return result


class FakeProvider:
    """Deterministic provider for tests and evals: returns canned or computed responses."""

    def __init__(self, respond: Callable[[str, dict], dict] | None = None, fail_with: Exception | None = None):
        self.respond = respond or (lambda model, payload: {})
        self.fail_with = fail_with
        self.calls: list[tuple[str, dict]] = []

    def generate(self, model: str, system: str, payload: dict, schema: dict) -> dict:
        self.calls.append((model, payload))
        if self.fail_with:
            raise self.fail_with
        return self.respond(model, payload)
