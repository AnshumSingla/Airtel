"""The PWA's cache rules (see app/security/static.py for why they matter)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.static import PwaStaticFiles


def make_app(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (tmp_path / "sw.js").write_text("// sw", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.mount("/", PwaStaticFiles(directory=tmp_path, html=True))
    return TestClient(app)


def test_shell_files_always_revalidate(tmp_path):
    c = make_app(tmp_path)
    for path in ("/", "/index.html", "/sw.js"):
        assert c.get(path).headers["cache-control"] == "no-cache", path


def test_hashed_assets_are_cached_forever(tmp_path):
    h = make_app(tmp_path).get("/assets/index-abc123.js").headers
    assert h["cache-control"] == "public, max-age=31536000, immutable"


def test_revalidation_is_cheap(tmp_path):
    c = make_app(tmp_path)
    etag = c.get("/").headers["etag"]
    assert c.get("/", headers={"If-None-Match": etag}).status_code == 304
