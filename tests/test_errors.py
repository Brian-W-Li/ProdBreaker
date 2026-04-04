"""Graceful failure tests — bad inputs must return clean JSON, never a stack trace."""


def test_404_returns_json(db_client):
    response = db_client.get("/does-not-exist")
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "Not Found"


def test_405_returns_json(db_client):
    response = db_client.post("/health")
    assert response.status_code == 405
    data = response.get_json()
    assert data["error"] == "Method Not Allowed"


def test_404_has_no_html(db_client):
    response = db_client.get("/definitely/not/a/route")
    assert response.content_type == "application/json"
    assert b"<!DOCTYPE" not in response.data
    assert b"Traceback" not in response.data
