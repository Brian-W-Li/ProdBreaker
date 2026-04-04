"""Tests for /products route — happy path and DB failure (chaos)."""
from unittest.mock import MagicMock, patch

from peewee import OperationalError


def test_products_returns_200(client):
    mock_product = MagicMock()
    mock_product.id = 1
    mock_product.name = "Widget"
    mock_product.category = "Tools"
    mock_product.price = 9.99
    mock_product.stock = 50

    with patch("app.routes.products.Product.select") as mock_select:
        mock_select.return_value = [mock_product]
        with patch("app.routes.products.model_to_dict", return_value={
            "id": 1, "name": "Widget", "category": "Tools", "price": 9.99, "stock": 50
        }):
            response = client.get("/products")

    assert response.status_code == 200


def test_products_returns_list(client):
    with patch("app.routes.products.Product.select") as mock_select:
        mock_select.return_value = []
        response = client.get("/products")

    assert response.status_code == 200
    assert response.get_json() == []


def test_products_db_down_returns_503(client):
    """Chaos: database goes away mid-request. Must return 503 JSON, not 500 crash."""
    with patch("app.routes.products.Product.select", side_effect=OperationalError("connection lost")):
        response = client.get("/products")

    assert response.status_code == 503
    data = response.get_json()
    assert data["error"] == "Service Unavailable"
    assert b"Traceback" not in response.data


def test_products_db_down_no_html(client):
    """Chaos: response must be JSON even when DB is dead."""
    with patch("app.routes.products.Product.select", side_effect=OperationalError("timeout")):
        response = client.get("/products")

    assert response.content_type == "application/json"
    assert b"<!DOCTYPE" not in response.data
