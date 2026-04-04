import io
from unittest.mock import MagicMock, patch

import pytest
from peewee import SqliteDatabase
from dotenv import load_dotenv
from app import create_app
from app.database import db
from app.models.user import User
from app.models.url import Url
from app.models.event import Event
from app.models.product import Product

load_dotenv()
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

@pytest.fixture(scope="session")
def app():
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    db.connect()  # keep connection open for the whole session so :memory: isn't destroyed
    app = create_app()  # init_db is skipped; create_tables runs on the open connection
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def db_client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Wipe tables before each test."""
    with app.app_context():
        Event.delete().execute()
        Url.delete().execute()
        User.delete().execute()
    yield
    with app.app_context():
        Event.delete().execute()
        Url.delete().execute()
        User.delete().execute()


@pytest.fixture
def sample_user(app):
    with app.app_context():
        return User.create(username="testuser", email="test@example.com")


@pytest.fixture
def sample_url(sample_user):
    return Url.create(
        user=sample_user,
        short_code="abc123",
        original_url="https://google.com",
        title="Google",
        is_active=True
    )

def make_user(client, username, email):
    resp = client.post("/users", json={"username": username, "email": email})
    return resp.get_json()

def make_url(client, user_id, original_url="https://example.com"):
    resp = client.post("/urls", json={
        "user_id": user_id,
        "original_url": original_url,
        "title": "Test URL"
    })
    return resp.get_json()

def make_csv(data):
    lines = []
    for row in data:
        lines.append(",".join(map(str, row)))
    return "\n".join(lines).encode("utf-8")