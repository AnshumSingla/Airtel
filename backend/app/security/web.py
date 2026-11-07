"""Web security for the owner journey (POLICIES.md §13).

- Session binding: starting an advisor session sets ``udyam_sid`` (HttpOnly,
  SameSite=Lax, Secure over HTTPS, 24 h). Every owner route checks that the
  session, KYC case or order it touches belongs to that cookie; knowing an id
  is not enough.
- CSRF: every state-changing /api request needs an ``X-CSRF-Token`` header that
  equals HMAC(server secret, session cookie). The expected value is computed from
  the HttpOnly session cookie, so it can't be undermined by stale, duplicated or
  unreadable JS-visible cookies. The app gets its token from the start-session
  response, the readable ``udyam_csrf`` cookie, or ``GET /api/csrf``. An ``Origin``
  header, when present, must be this app's origin or an allowed dev origin.
  Starting a session is exempt (there is no session yet to protect).
- Per-IP rate limits, and security headers on every response.
CORS stays off: the PWA is served from the same origin.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log = logging.getLogger("udyam")

# Signs CSRF tokens. Random per process unless UDYAM_CSRF_SECRET is set (sessions don't outlive a
# restart of the demo anyway; set it to keep tokens valid across restarts).
_SECRET = (os.environ.get("UDYAM_CSRF_SECRET") or secrets.token_hex(32)).encode()

SID_COOKIE = "udyam_sid"
STAFF_COOKIE = "udyam_staff"
CSRF_COOKIE = "udyam_csrf"
CSRF_HEADER = "x-csrf-token"
SESSION_MAX_AGE = 24 * 3600
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
STAFF_CSRF_COOKIE = "udyam_staff_csrf"
CSRF_EXEMPT = {("POST", "/api/advisor/sessions"), ("POST", "/api/bo/login")}

DEFAULT_LIMITS = {"start": (10, 60), "login": (10, 60), "upload": (30, 60), "api": (240, 60)}   # (requests, seconds) per IP

CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
       "form-action 'self'")


def csrf_for(session_token: str) -> str:
    """The CSRF token for a session (or "staff:"-prefixed staff session) cookie value."""
    mac = hmac.new(_SECRET, session_token.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")[:32]


def _is_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


def set_session_cookies(request: Request, response: Response, sid: str) -> None:
    secure = _is_https(request)
    response.set_cookie(SID_COOKIE, sid, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax",
                        secure=secure, path="/")
    # A convenience copy for the page's script. The server doesn't trust it: it recomputes the token
    # from the HttpOnly session cookie and compares that with the header.
    response.set_cookie(CSRF_COOKIE, csrf_for(sid), max_age=SESSION_MAX_AGE, httponly=False,
                        samesite="lax", secure=secure, path="/")


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SID_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def cookie_sid(request: Request) -> str | None:
    return request.cookies.get(SID_COOKIE)


def require_owner(request: Request, sid: str) -> None:
    """404, not 403, so an attacker can't tell whether someone else's session exists."""
    own = cookie_sid(request)
    if not own or not hmac.compare_digest(own, sid):
        raise HTTPException(404, "session not found or expired")


class RateLimiter:
    def __init__(self, limits: dict[str, tuple[int, int]] | None = None):
        if limits is None:
            # UDYAM_RATE_LIMIT_SCALE multiplies the defaults (the test suite raises it; production leaves it at 1).
            scale = float(os.environ.get("UDYAM_RATE_LIMIT_SCALE", "1"))
            limits = {g: (max(1, int(n * scale)), w) for g, (n, w) in DEFAULT_LIMITS.items()}
        self.limits = dict(limits)
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, ip: str, group: str) -> float | None:
        """None if allowed, else seconds until the next request is allowed."""
        n, window = self.limits[group]
        now = time.monotonic()
        with self._lock:
            q = self._hits[(ip, group)]
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= n:
                return window - (now - q[0])
            q.append(now)
            return None


def _group(method: str, path: str) -> str:
    if method == "POST" and path == "/api/advisor/sessions":
        return "start"
    if method == "POST" and path == "/api/bo/login":
        return "login"
    if path.startswith("/api/kyc/cases/") and path.endswith("/documents"):
        return "upload"
    return "api"


def allowed_origins() -> set[str]:
    extra = os.environ.get("UDYAM_ALLOWED_ORIGINS", "")
    dev = {"http://localhost:5173", "http://127.0.0.1:5173"}   # Vite dev server (proxies /api)
    return {o.strip() for o in extra.split(",") if o.strip()} | dev


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        path, method = request.url.path, request.method
        if path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            wait = self.limiter.check(ip, _group(method, path))
            if wait is not None:
                return self._headers(JSONResponse({"detail": "too many requests"}, status_code=429,
                                                  headers={"Retry-After": str(int(wait) + 1)}))
            if method in MUTATING:
                origin = request.headers.get("origin")
                own = f"{request.url.scheme}://{request.url.netloc}"
                if origin and origin != own and origin not in allowed_origins():
                    return self._headers(JSONResponse({"detail": "cross-site request refused"}, status_code=403))
                if (method, path) not in CSRF_EXEMPT:
                    staff = path.startswith("/api/bo/")
                    session = request.cookies.get(STAFF_COOKIE if staff else SID_COOKIE, "")
                    token = request.headers.get(CSRF_HEADER, "")
                    if not session:
                        log.warning("csrf refused: %s has no session cookie (cookies blocked or expired?)", path)
                        return self._headers(JSONResponse(
                            {"detail": "no session cookie: your browser must allow cookies for this site",
                             "code": "no_session_cookie"}, status_code=403))
                    expected = csrf_for(("staff:" if staff else "") + session)
                    if not token or not hmac.compare_digest(token, expected):
                        log.warning("csrf refused: %s header_present=%s", path, bool(token))
                        return self._headers(JSONResponse({"detail": "missing or invalid CSRF token",
                                                           "code": "bad_csrf"}, status_code=403))
        return self._headers(await call_next(request))

    @staticmethod
    def _headers(response):
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Content-Security-Policy", CSP)
        h.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        if response.headers.get("content-type", "").startswith("application/json"):
            h.setdefault("Cache-Control", "no-store")
        return response
