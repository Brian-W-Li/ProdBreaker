from flask import Blueprint, jsonify, make_response
from peewee import OperationalError, ProgrammingError
from playhouse.shortcuts import model_to_dict

from app.cache import cache_get, cache_set
from app.models.product import Product

products_bp = Blueprint("products", __name__)

CACHE_KEY = "products:all"
CACHE_TTL = 60  # seconds


@products_bp.route("/products")
def list_products():
    cached = cache_get(CACHE_KEY)
    if cached is not None:
        response = make_response(jsonify(cached))
        response.headers["X-Cache"] = "HIT"
        return response

    try:
        products = Product.select()
        data = [model_to_dict(p) for p in products]
    except (OperationalError, ProgrammingError):
        return jsonify(error="Service Unavailable", message="Database is unavailable"), 503

    cache_set(CACHE_KEY, data, ttl=CACHE_TTL)
    response = make_response(jsonify(data))
    response.headers["X-Cache"] = "MISS"
    return response
