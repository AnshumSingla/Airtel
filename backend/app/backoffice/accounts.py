"""Staff accounts and staff sessions (POLICIES.md §11, §13).

- Seeded accounts per role. Each password comes from STAFF_PASSWORD_<USERNAME>.
  In demo mode, a missing password is generated at boot and written only to a
  git-ignored local file (backend/.demo-staff-credentials.txt), never to logs.
  Outside demo mode, an account without a password is disabled.
- Argon2id hashes (argon2-cffi); 5 failed logins lock the account for 15 min.
- Server-side staff sessions: 30 min idle, 8 h absolute; logout deletes the row;
  changing a password revokes that account's sessions.
"""

from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, delete, select, update

PARTNERS = {"P-SHARMA": "Sharma Telecom", "P-METRO": "Metro Connect"}
REFERRAL_CODES = {"sharma": "P-SHARMA", "metro": "P-METRO"}
ACCEL_SALES = "accel_sales"
TEAM_NAMES = {ACCEL_SALES: "Accel Business sales", **PARTNERS}

ROLES = {"sales_agent", "partner", "kyc_reviewer", "admin"}
SEED = [
    ("sales1", "sales_agent", None, "Sales agent"),
    ("partner_sharma", "partner", "P-SHARMA", "Sharma Telecom (partner)"),
    ("partner_metro", "partner", "P-METRO", "Metro Connect (partner)"),
    ("reviewer1", "kyc_reviewer", None, "KYC reviewer"),
    ("admin1", "admin", None, "Admin"),
]

IDLE = timedelta(minutes=30)
ABSOLUTE = timedelta(hours=8)
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)

staff_metadata = MetaData()
staff_sessions = Table(
    "staff_sessions", staff_metadata,
    Column("token", String, primary_key=True),
    Column("username", String, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class Staff:
    username: str
    role: str
    partner_id: str | None
    display: str


class LoginFailed(PermissionError):
    pass


class AccountLocked(PermissionError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class StaffDirectory:
    def __init__(self, engine: Engine, demo: bool, credentials_file: Path | None = None,
                 passwords: dict[str, str] | None = None, reset: bool = True):
        self.engine = engine
        self._ph = PasswordHasher()   # Argon2id with the library's current defaults
        self._hashes: dict[str, str] = {}
        self.accounts: dict[str, Staff] = {}
        self._failures: dict[str, tuple[int, datetime | None]] = {}
        self._lock = threading.Lock()
        generated: dict[str, str] = {}
        for username, role, partner, display in SEED:
            pw = (passwords or {}).get(username) or os.environ.get(f"STAFF_PASSWORD_{username.upper()}")
            if not pw and demo:
                pw = secrets.token_urlsafe(12)
                generated[username] = pw
            if not pw:
                continue   # disabled outside demo mode
            self._hashes[username] = self._ph.hash(pw)
            self.accounts[username] = Staff(username, role, partner, display)
        if generated and credentials_file is not None:
            credentials_file.write_text(
                "# Demo staff credentials, generated at server start. Synthetic demo only. Not committed.\n"
                + "".join(f"{u}\t{p}\n" for u, p in generated.items()), encoding="utf-8")
        self.generated_usernames = sorted(generated)
        if reset:
            staff_metadata.drop_all(engine)
        staff_metadata.create_all(engine)

    # ------------------------------------------------------------ login
    def login(self, username: str, password: str) -> str:
        with self._lock:
            count, until = self._failures.get(username, (0, None))
            if until and _now() < until:
                raise AccountLocked("account locked, try again later")
        ok = False
        if username in self._hashes:
            try:
                ok = self._ph.verify(self._hashes[username], password)
            except VerificationError:
                ok = False
        else:
            # Same work for unknown users, so timing doesn't reveal which usernames exist.
            try:
                self._ph.verify(self._ph.hash("x"), "y")
            except VerificationError:
                pass
        with self._lock:
            if not ok:
                count = self._failures.get(username, (0, None))[0] + 1
                self._failures[username] = (count, _now() + LOCKOUT if count >= MAX_FAILURES else None)
                raise LoginFailed("wrong username or password")
            self._failures.pop(username, None)
        token = secrets.token_urlsafe(32)
        now = _now()
        with self.engine.begin() as conn:
            conn.execute(staff_sessions.insert().values(token=token, username=username, created_at=now, last_seen=now))
        return token

    def session(self, token: str | None) -> Staff | None:
        if not token:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(select(staff_sessions).where(staff_sessions.c.token == token)).mappings().first()
        if row is None or row["username"] not in self.accounts:
            return None
        now = _now()
        if now - _aware(row["last_seen"]) > IDLE or now - _aware(row["created_at"]) > ABSOLUTE:
            self.logout(token)
            return None
        with self.engine.begin() as conn:
            conn.execute(update(staff_sessions).where(staff_sessions.c.token == token).values(last_seen=now))
        return self.accounts[row["username"]]

    def logout(self, token: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(staff_sessions).where(staff_sessions.c.token == token))

    def set_password(self, username: str, password: str) -> None:
        """Change a password and revoke all of that account's sessions."""
        self._hashes[username] = self._ph.hash(password)
        with self.engine.begin() as conn:
            conn.execute(delete(staff_sessions).where(staff_sessions.c.username == username))
