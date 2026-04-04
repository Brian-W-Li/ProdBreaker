from unittest.mock import MagicMock, patch

import pytest

from app import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    with patch("peewee.Psycopg2Adapter.connect", return_value=MagicMock()):
        with app.test_client() as c:
            yield c
