# type: ignore
from flask import Blueprint, jsonify, request
from app.models.user import User
from datetime import datetime

users_bp = Blueprint("users", __name__)


@users_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()

    if not data or not data.get("username") or not data.get("email"):
        return jsonify(error="Missing 'username' or 'email'"), 400

    if User.select().where(User.username == data["username"]).exists():
        return jsonify(error="Username already taken"), 409

    if User.select().where(User.email == data["email"]).exists():
        return jsonify(error="Email already registered"), 409

    user = User.create(username=data["username"], email=data["email"])
    return jsonify(id=user.id, username=user.username, email=user.email), 201


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    return jsonify(id=user.id, username=user.username, email=user.email, created_at=str(user.created_at))

@users_bp.route("/users/<int:user_id>/urls", methods=["GET"])
def user_urls(user_id):
    from app.models.url import URL
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    urls = URL.select().where(URL.user == user)
    return jsonify([{
        "short_code": u.short_code,
        "original_url": u.original_url,
        "title": u.title,
        "is_active": u.is_active,
        "created_at": str(u.created_at)
    } for u in urls])