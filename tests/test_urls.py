def test_shorten_url(client, sample_user):
    res = client.post("/shorten", json={
        "url": "https://example.com",
        "user_id": sample_user.id,
        "title": "Example"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert "short_code" in data
    assert "url" in data


def test_shorten_url_missing_url(client, sample_user):
    res = client.post("/shorten", json={"user_id": sample_user.id})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_shorten_url_missing_user_id(client):
    res = client.post("/shorten", json={"url": "https://example.com"})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_shorten_url_invalid_url(client, sample_user):
    res = client.post("/shorten", json={
        "url": "not-a-url",
        "user_id": sample_user.id
    })
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_shorten_url_user_not_found(client):
    res = client.post("/shorten", json={
        "url": "https://example.com",
        "user_id": 99999
    })
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_redirect_url(client, sample_url):
    res = client.get(f"/{sample_url.short_code}")
    assert res.status_code == 302


def test_redirect_url_not_found(client):
    res = client.get("/doesnotexist")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_redirect_inactive_url(client, sample_url):
    sample_url.is_active = False
    sample_url.save()
    res = client.get(f"/{sample_url.short_code}")
    assert res.status_code == 410
    assert "error" in res.get_json()


def test_url_stats(client, sample_url):
    res = client.get(f"/stats/{sample_url.short_code}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["short_code"] == sample_url.short_code
    assert data["clicks"] == 0


def test_url_stats_click_count(client, sample_url):
    client.get(f"/{sample_url.short_code}")
    client.get(f"/{sample_url.short_code}")
    res = client.get(f"/stats/{sample_url.short_code}")
    assert res.get_json()["clicks"] == 2


def test_url_stats_not_found(client):
    res = client.get("/stats/doesnotexist")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_deactivate_url(client, sample_url):
    res = client.delete(f"/urls/{sample_url.short_code}")
    assert res.status_code == 200
    sample_url = sample_url.__class__.get_by_id(sample_url.id)
    assert sample_url.is_active == False


def test_deactivate_url_not_found(client):
    res = client.delete("/urls/doesnotexist")
    assert res.status_code == 404
    assert "error" in res.get_json()