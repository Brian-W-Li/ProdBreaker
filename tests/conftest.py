import pytest
from dotenv import load_dotenv
from app import create_app
from app.database import db
from app.models.user import User
from app.models.url import URL
from app.models.event import Event

load_dotenv()


@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Wipe tables before each test."""
    with app.app_context():
        db.create_tables([User, URL, Event], safe=True)
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