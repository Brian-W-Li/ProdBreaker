def test_health_returns_200(db_client):
    response = db_client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok(db_client):
    data = db_client.get("/health").get_json()
    assert data == {"status": "ok"}
