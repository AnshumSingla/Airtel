from __future__ import annotations

import sys
from pathlib import Path

import os

import pytest

# Many sessions are started from one test process; keep the real limits for test_security.py only.
os.environ.setdefault("UDYAM_RATE_LIMIT_SCALE", "1000")

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DATA_DIR = REPO_ROOT / "data" / "raw"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def seeded_engine(tmp_path_factory, data_dir):
    from app.data.seed import make_engine, seed

    db = tmp_path_factory.mktemp("db") / "test.db"
    engine = make_engine(f"sqlite:///{db.as_posix()}")
    seed(engine, data_dir)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def lex(seeded_engine):
    from app.advisor.lexicon import build_lexicon

    return build_lexicon(seeded_engine)


@pytest.fixture(scope="session")
def cat(data_dir):
    from app.catalogue.models import load_catalogue_csv

    return load_catalogue_csv(data_dir / "product_catalogue.csv")


def make_client(app):
    """A TestClient that behaves like the PWA: it echoes the CSRF cookie in X-CSRF-Token."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    def add_csrf(request):
        name = "udyam_staff_csrf" if request.url.path.startswith("/api/bo/") else "udyam_csrf"
        token = client.cookies.get(name)
        if token and "x-csrf-token" not in request.headers:
            request.headers["x-csrf-token"] = token

    client.event_hooks["request"].append(add_csrf)
    return client
