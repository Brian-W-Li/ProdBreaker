"""Tests for /products route — happy path, caching, and DB failure (chaos)."""
from unittest.mock import MagicMock, patch

from peewee import OperationalError

PRODUCT_DICT = {"id": 1, "name": "Widget", "category": "Tools", "price": 9.99, "stock": 50}


def _no_cache(monkeypatch):
    """Patch cache_get to always return None (cache miss) and cache_set to no-op."""
    monkeypatch.setattr("app.routes.products.cache_get", lambda key: None)
    monkeypatch.setattr("app.routes.products.cache_set", lambda key, val, ttl=60: None)


def test_products_returns_200(db_client, monkeypatch):
    _no_cache(monkeypatch)
    with patch("app.routes.products.Product.select") as mock_select:
        mock_select.return_value = [MagicMock()]
        with patch("app.routes.products.model_to_dict", return_value=PRODUCT_DICT):
            response = db_client.get("/products")
    assert response.status_code == 200


def test_products_returns_list(db_client, monkeypatch):
    _no_cache(monkeypatch)
    with patch("app.routes.products.Product.select") as mock_select:
        mock_select.return_value = []
        response = db_client.get("/products")
    assert response.status_code == 200
    assert response.get_json() == []


def test_products_cache_miss_header(db_client, monkeypatch):
    _no_cache(monkeypatch)
    with patch("app.routes.products.Product.select") as mock_select:
        mock_select.return_value = []
        response = db_client.get("/products")
    assert response.headers.get("X-Cache") == "MISS"


def test_products_cache_hit(db_client, monkeypatch):
    monkeypatch.setattr("app.routes.products.cache_get", lambda key: [PRODUCT_DICT])
    response = db_client.get("/products")
    assert response.status_code == 200
    assert response.headers.get("X-Cache") == "HIT"
    assert response.get_json() == [PRODUCT_DICT]


def test_products_db_down_returns_503(db_client, monkeypatch):
    """Chaos: database goes away mid-request. Must return 503 JSON, not 500 crash."""
    _no_cache(monkeypatch)
    with patch("app.routes.products.Product.select", side_effect=OperationalError("connection lost")):
        response = db_client.get("/products")
    assert response.status_code == 503
    assert response.get_json()["error"] == "Service Unavailable"
    assert b"Traceback" not in response.data


def test_products_db_down_no_html(db_client, monkeypatch):
    """Chaos: response must be JSON even when DB is dead."""
    _no_cache(monkeypatch)
    with patch("app.routes.products.Product.select", side_effect=OperationalError("timeout")):
        response = db_client.get("/products")
    assert response.content_type == "application/json"
    assert b"<!DOCTYPE" not in response.data
