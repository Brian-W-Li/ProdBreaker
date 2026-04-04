"""Tests for /users — CRUD + bulk CSV import."""
import io

from tests.conftest import make_csv, make_user


# ── POST /users ───────────────────────────────────────────────────────────────

def test_create_user_201(db_client):
    resp = db_client.post("/users", json={"username": "alice", "email": "alice@example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "created_at" in data


def test_create_user_invalid_username_type(db_client):
    resp = db_client.post("/users", json={"username": 123, "email": "a@b.com"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Bad Request"


def test_create_user_invalid_email_type(db_client):
    resp = db_client.post("/users", json={"username": "alice", "email": None})
    assert resp.status_code == 400


def test_create_user_duplicate_username(db_client):
    db_client.post("/users", json={"username": "bob", "email": "bob@example.com"})
    resp = db_client.post("/users", json={"username": "bob", "email": "other@example.com"})
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "Conflict"


def test_create_user_duplicate_email(db_client):
    db_client.post("/users", json={"username": "carol", "email": "shared@example.com"})
    resp = db_client.post("/users", json={"username": "carol2", "email": "shared@example.com"})
    assert resp.status_code == 409


# ── GET /users ────────────────────────────────────────────────────────────────

def test_list_users_empty(db_client):
    resp = db_client.get("/users")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_users_returns_all(db_client):
    make_user(db_client, "u1", "u1@x.com")
    make_user(db_client, "u2", "u2@x.com")
    resp = db_client.get("/users")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_list_users_pagination(db_client):
    for i in range(5):
        make_user(db_client, f"user{i}", f"user{i}@x.com")
    resp = db_client.get("/users?page=1&per_page=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_list_users_page2(db_client):
    for i in range(5):
        make_user(db_client, f"puser{i}", f"puser{i}@x.com")
    p1 = db_client.get("/users?page=1&per_page=3").get_json()
    p2 = db_client.get("/users?page=2&per_page=3").get_json()
    assert len(p1) == 3
    assert len(p2) == 2
    assert {u["id"] for u in p1}.isdisjoint({u["id"] for u in p2})


# ── GET /users/<id> ───────────────────────────────────────────────────────────

def test_get_user_by_id(db_client):
    user = make_user(db_client, "dave", "dave@example.com")
    resp = db_client.get(f"/users/{user['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "dave"


def test_get_user_not_found(db_client):
    resp = db_client.get("/users/9999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Not Found"


# ── PUT /users/<id> ───────────────────────────────────────────────────────────

def test_update_user_username(db_client):
    user = make_user(db_client, "old", "old@example.com")
    resp = db_client.put(f"/users/{user['id']}", json={"username": "new"})
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "new"
    assert resp.get_json()["email"] == "old@example.com"


def test_update_user_email(db_client):
    user = make_user(db_client, "eve", "eve@example.com")
    resp = db_client.put(f"/users/{user['id']}", json={"email": "eve2@example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "eve2@example.com"


def test_update_user_not_found(db_client):
    resp = db_client.put("/users/9999", json={"username": "x"})
    assert resp.status_code == 404


def test_update_user_invalid_type(db_client):
    user = make_user(db_client, "frank", "frank@example.com")
    resp = db_client.put(f"/users/{user['id']}", json={"username": 999})
    assert resp.status_code == 400


# ── POST /users/bulk ──────────────────────────────────────────────────────────

def test_bulk_import_basic(db_client):
    csv_data = make_csv([
        ["username", "email"],
        ["bulk1", "bulk1@example.com"],
        ["bulk2", "bulk2@example.com"],
    ])
    resp = db_client.post("/users/bulk", data={"file": (io.BytesIO(csv_data), "users.csv")})
    assert resp.status_code == 201
    assert resp.get_json()["imported"] == 2


def test_bulk_import_with_created_at(db_client):
    csv_data = make_csv([
        ["username", "email", "created_at"],
        ["ts1", "ts1@x.com", "2024-04-09T02:51:03"],
    ])
    resp = db_client.post("/users/bulk", data={"file": (io.BytesIO(csv_data), "users.csv")})
    assert resp.status_code == 201
    users = db_client.get("/users").get_json()
    match = next(u for u in users if u["username"] == "ts1")
    assert match["created_at"].startswith("2024-04-09")


def test_bulk_import_skips_duplicates(db_client):
    make_user(db_client, "existing", "existing@x.com")
    csv_data = make_csv([
        ["username", "email"],
        ["existing", "existing@x.com"],
        ["newone", "newone@x.com"],
    ])
    resp = db_client.post("/users/bulk", data={"file": (io.BytesIO(csv_data), "users.csv")})
    assert resp.status_code == 201
    assert resp.get_json()["imported"] == 1


def test_bulk_import_no_file(db_client):
    resp = db_client.post("/users/bulk")
    assert resp.status_code == 400
