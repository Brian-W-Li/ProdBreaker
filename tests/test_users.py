def test_create_user(client):
    res = client.post("/users", json={
        "username": "alice",
        "email": "alice@example.com"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"


def test_create_user_missing_fields(client):
    res = client.post("/users", json={"username": "alice"})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_create_user_duplicate_username(client, sample_user):
    res = client.post("/users", json={
        "username": "testuser",
        "email": "other@example.com"
    })
    assert res.status_code == 409


def test_create_user_duplicate_email(client, sample_user):
    res = client.post("/users", json={
        "username": "other",
        "email": "test@example.com"
    })
    assert res.status_code == 409


def test_get_user(client, sample_user):
    res = client.get(f"/users/{sample_user.id}")
    assert res.status_code == 200
    assert res.get_json()["username"] == "testuser"


def test_get_user_not_found(client):
    res = client.get("/users/99999")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_get_user_urls(client, sample_user, sample_url):
    res = client.get(f"/users/{sample_user.id}/urls")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["short_code"] == "abc123"