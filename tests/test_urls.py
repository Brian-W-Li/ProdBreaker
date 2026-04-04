"""Tests for /urls — CRUD, short code generation, event creation, filtering."""
from tests.conftest import make_url, make_user


# ── POST /urls ────────────────────────────────────────────────────────────────

def test_create_url_201(db_client):
    user = make_user(db_client, "alice", "alice@x.com")
    resp = db_client.post("/urls", json={
        "user_id": user["id"],
        "original_url": "https://example.com",
        "title": "Example",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user_id"] == user["id"]
    assert data["original_url"] == "https://example.com"
    assert data["title"] == "Example"
    assert data["is_active"] is True
    assert len(data["short_code"]) == 6
    assert "created_at" in data
    assert "updated_at" in data


def test_create_url_generates_unique_short_codes(db_client):
    user = make_user(db_client, "bob", "bob@x.com")
    codes = set()
    for i in range(5):
        data = make_url(db_client, user["id"], f"https://example.com/{i}")
        codes.add(data["short_code"])
    assert len(codes) == 5


def test_create_url_missing_user(db_client):
    resp = db_client.post("/urls", json={
        "user_id": 9999,
        "original_url": "https://example.com",
    })
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Not Found"


def test_create_url_missing_fields(db_client):
    resp = db_client.post("/urls", json={"user_id": 1})
    assert resp.status_code == 400


def test_create_url_creates_event(db_client):
    user = make_user(db_client, "carol", "carol@x.com")
    url = make_url(db_client, user["id"])
    events = db_client.get("/events").get_json()
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["url_id"] == url["id"]
    assert events[0]["user_id"] == user["id"]
    assert events[0]["details"]["short_code"] == url["short_code"]


# ── GET /urls ─────────────────────────────────────────────────────────────────

def test_list_urls_empty(db_client):
    resp = db_client.get("/urls")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_urls_all(db_client):
    user = make_user(db_client, "dave", "dave@x.com")
    make_url(db_client, user["id"], "https://a.com")
    make_url(db_client, user["id"], "https://b.com")
    resp = db_client.get("/urls")
    assert len(resp.get_json()) == 2


def test_list_urls_filter_by_user(db_client):
    u1 = make_user(db_client, "u1", "u1@x.com")
    u2 = make_user(db_client, "u2", "u2@x.com")
    make_url(db_client, u1["id"], "https://u1.com")
    make_url(db_client, u2["id"], "https://u2.com")
    resp = db_client.get(f"/urls?user_id={u1['id']}")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["user_id"] == u1["id"]


# ── GET /urls/<id> ────────────────────────────────────────────────────────────

def test_get_url_by_id(db_client):
    user = make_user(db_client, "eve", "eve@x.com")
    url = make_url(db_client, user["id"])
    resp = db_client.get(f"/urls/{url['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == url["id"]


def test_get_url_not_found(db_client):
    resp = db_client.get("/urls/9999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Not Found"


# ── PUT /urls/<id> ────────────────────────────────────────────────────────────

def test_update_url_title(db_client):
    user = make_user(db_client, "frank", "frank@x.com")
    url = make_url(db_client, user["id"])
    resp = db_client.put(f"/urls/{url['id']}", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "New Title"


def test_update_url_is_active(db_client):
    user = make_user(db_client, "grace", "grace@x.com")
    url = make_url(db_client, user["id"])
    resp = db_client.put(f"/urls/{url['id']}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.get_json()["is_active"] is False


def test_update_url_updates_timestamp(db_client):
    user = make_user(db_client, "hank", "hank@x.com")
    url = make_url(db_client, user["id"])
    original_updated_at = url["updated_at"]
    resp = db_client.put(f"/urls/{url['id']}", json={"title": "Changed"})
    assert resp.get_json()["updated_at"] != original_updated_at


def test_update_url_creates_event(db_client):
    user = make_user(db_client, "ivan", "ivan@x.com")
    url = make_url(db_client, user["id"])
    db_client.put(f"/urls/{url['id']}", json={"title": "Updated"})
    events = db_client.get("/events").get_json()
    types = [e["event_type"] for e in events]
    assert "created" in types
    assert "updated" in types


def test_update_url_not_found(db_client):
    resp = db_client.put("/urls/9999", json={"title": "x"})
    assert resp.status_code == 404
