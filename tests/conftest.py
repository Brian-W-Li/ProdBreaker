import io
from unittest.mock import MagicMock, patch

import pytest
from peewee import SqliteDatabase

# Patch cache to no-ops for all tests — prevents cross-test pollution via real Redis
_cache_patches = [
    patch("app.cache.cache_get", return_value=None),
    patch("app.cache.cache_set", return_value=None),
]


def pytest_configure(config):
    for p in _cache_patches:
        p.start()


def pytest_unconfigure(config):
    for p in _cache_patches:
        p.stop()


@pytest.fixture
def app():
    """App fixture with mocked Postgres — used by existing tests (no real DB)."""
    with patch("peewee.Psycopg2Adapter.connect", return_value=MagicMock()):
        from app import create_app
        application = create_app()
        application.config["TESTING"] = True
        yield application


@pytest.fixture
def client(app):
    """Flask test client backed by mocked Postgres."""
    with patch("peewee.Psycopg2Adapter.connect", return_value=MagicMock()):
        with app.test_client() as c:
            yield c


@pytest.fixture
def db_client():
    """
    Flask test client backed by a fresh in-memory SQLite DB per test.

    Strategy:
    1. Create app with Postgres adapter mocked (prevents connection errors).
    2. After creation, swap the DatabaseProxy to point at SQLite.
    3. Patch the before_request connect to use SQLite's connect.
    4. Tables are created on SQLite fresh for each test.
    """
    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User
    from app.models.product import Product
    from app.database import db

    test_db = SqliteDatabase(":memory:")

    mock_conn = MagicMock()
    with patch("peewee.Psycopg2Adapter.connect", return_value=mock_conn):
        from app import create_app
        application = create_app()
        application.config["TESTING"] = True

    # Swap the proxy to SQLite now that the app is built
    test_db.bind([User, Url, Event, Product], bind_refs=False, bind_backrefs=False)
    test_db.connect()
    test_db.create_tables([User, Url, Event, Product])
    db.initialize(test_db)

    # Patch the before_request hook's db reference so it uses test_db
    # The hook calls db.connect(reuse_if_open=True) — db is now SQLite, that's fine.
    # But we need to make sure db.close() doesn't close SQLite between requests.
    # We do this by patching the teardown to no-op for tests.
    original_close = test_db.close
    test_db.close = lambda: None  # prevent teardown from closing between requests

    with application.test_client() as c:
        yield c

    test_db.close = original_close
    if not test_db.is_closed():
        test_db.drop_tables([User, Url, Event, Product])
        test_db.close()


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_user(db_client, username="testuser", email="test@example.com"):
    resp = db_client.post("/users", json={"username": username, "email": email})
    return resp.get_json()


def make_url(db_client, user_id, original_url="https://example.com", title="Test"):
    resp = db_client.post("/urls", json={
        "user_id": user_id,
        "original_url": original_url,
        "title": title,
    })
    return resp.get_json()


def make_csv(rows):
    fields = list(rows[0].keys())
    lines = [",".join(fields)]
    for row in rows:
        lines.append(",".join(str(row[f]) for f in fields))
    return "\n".join(lines).encode()
