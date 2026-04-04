import io
from unittest.mock import MagicMock, patch

import pytest
from peewee import SqliteDatabase
from dotenv import load_dotenv
from app import create_app
from app.database import db
from app.models.user import User
from app.models.url import URL
from app.models.event import Event

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
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Wipe tables before each test."""
    db.create_tables([User, URL, Event], safe=True)
    with app.app_context():
        Event.delete().execute()
        URL.delete().execute()
        User.delete().execute()
    yield
    with app.app_context():
        Event.delete().execute()
        URL.delete().execute()
        User.delete().execute()


@pytest.fixture
def sample_user(app):
    with app.app_context():
        return User.create(username="testuser", email="test@example.com")


@pytest.fixture
def sample_url(sample_user):
    return URL.create(
        user=sample_user,
        short_code="abc123",
        original_url="https://google.com",
        title="Google",
        is_active=True
    )