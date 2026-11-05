"""Encryption at rest for extracted KYC fields (POLICIES.md §13).

KYC_FIELD_KEYS is a comma-separated list of Fernet keys: the first encrypts,
all decrypt (MultiFernet), so rotation is "add a new first key, re-encrypt,
remove the old key". In demo mode without a key, an ephemeral key is made at
boot: fine for a demo that resets on restart, and reported by /api/health.
"""

from __future__ import annotations

import json
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class FieldCipher:
    def __init__(self, keys: list[str] | None = None):
        env = os.environ.get("KYC_FIELD_KEYS", "")
        keys = keys if keys is not None else [k.strip() for k in env.split(",") if k.strip()]
        self.ephemeral = not keys
        if self.ephemeral:
            keys = [Fernet.generate_key().decode()]
        self._f = MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])

    def encrypt(self, value) -> str:
        return self._f.encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()

    def decrypt(self, token: str):
        try:
            return json.loads(self._f.decrypt(token.encode()))
        except InvalidToken as exc:
            raise ValueError("cannot decrypt with the configured keys") from exc

    def rotate(self, token: str) -> str:
        return self._f.rotate(token.encode()).decode()
