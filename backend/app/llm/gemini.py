"""Gemini provider over the public REST API (generateContent with a JSON response schema).

Uses httpx, already a dependency, instead of an extra SDK. The key is sent in
the ``x-goog-api-key`` header, never in the URL, so it can't end up in logs.
Free tier: synthetic demo content only (POLICIES.md §5). Every call goes
through LLMClient, which allows only privacy-gated payloads.
"""

from __future__ import annotations

import json

import httpx

from app.llm.client import RateLimited, TransientError

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider:
    def __init__(self, api_key: str, timeout_s: float = 10.0, http: httpx.Client | None = None):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is empty")
        self._key = api_key
        self._http = http or httpx.Client(timeout=timeout_s)

    def generate(self, model: str, system: str, payload: dict, schema: dict) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema,
                                 "temperature": 0.2},
        }
        try:
            resp = self._http.post(API.format(model=model), json=body, headers={"x-goog-api-key": self._key})
        except httpx.TimeoutException as exc:
            raise TransientError("timeout") from exc
        except httpx.HTTPError as exc:
            raise TransientError(type(exc).__name__) from exc
        if resp.status_code == 429:
            raise RateLimited()
        if resp.status_code >= 500:
            raise TransientError(str(resp.status_code))
        if resp.status_code != 200:
            # 4xx other than 429: a bad key or request won't fix itself on retry.
            raise RateLimited()
        try:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, ValueError) as exc:
            raise TransientError("unparseable response") from exc
