from flask import Blueprint, jsonify
from peewee import OperationalError
from playhouse.shortcuts import model_to_dict

from app.models.product import Product

products_bp = Blueprint("products", __name__)


@products_bp.route("/products")
def list_products():
    try:
        products = Product.select()
        return jsonify([model_to_dict(p) for p in products])
    except OperationalError as e:
        return jsonify(error="Service Unavailable", message="Database is unavailable"), 503
