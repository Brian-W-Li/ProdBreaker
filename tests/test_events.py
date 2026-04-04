"""Tests for /events — listing, details parsing."""
from tests.conftest import make_url, make_user


def test_list_events_empty(db_client):
    resp = db_client.get("/events")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_events_after_url_create(db_client):
    user = make_user(db_client, "alice", "alice@x.com")
    url = make_url(db_client, user["id"])
    events = db_client.get("/events").get_json()
    assert len(events) == 1
    e = events[0]
    assert e["event_type"] == "created"
    assert e["url_id"] == url["id"]
    assert e["user_id"] == user["id"]
    assert isinstance(e["details"], dict)
    assert "short_code" in e["details"]
    assert "original_url" in e["details"]
    assert "timestamp" in e


def test_list_events_after_url_update(db_client):
    user = make_user(db_client, "bob", "bob@x.com")
    url = make_url(db_client, user["id"])
    db_client.put(f"/urls/{url['id']}", json={"title": "Updated"})
    events = db_client.get("/events").get_json()
    assert len(events) == 2
    assert events[1]["event_type"] == "updated"


def test_events_details_is_dict_not_string(db_client):
    user = make_user(db_client, "carol", "carol@x.com")
    make_url(db_client, user["id"])
    events = db_client.get("/events").get_json()
    assert isinstance(events[0]["details"], dict)
