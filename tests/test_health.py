def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok(client):
    data = client.get("/health").get_json()
    assert data == {"status": "ok"}
