import csv
import io
from datetime import datetime

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.cache import cache_get, cache_set
from app.database import db
from app.models.user import User

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _user_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@users_bp.route("/bulk", methods=["POST"])
def bulk_import():
    if "file" not in request.files:
        return jsonify(error="Bad Request", message="No file field in request"), 400

    file = request.files["file"]
    content = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    # Strip whitespace from field names
    reader.fieldnames = [f.strip() for f in reader.fieldnames] if reader.fieldnames else reader.fieldnames

    rows = []
    for row in reader:
        row = {k.strip(): v.strip() for k, v in row.items()}
        created_at = datetime.utcnow()
        if "created_at" in row and row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except ValueError:
                pass
        rows.append({
            "username": row.get("username", ""),
            "email": row.get("email", ""),
            "created_at": created_at,
        })

    imported = 0
    chunk_size = 100
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        for row_data in chunk:
            try:
                with db.atomic():
                    User.create(**row_data)
                    imported += 1
            except IntegrityError:
                pass

    return jsonify(imported=imported), 201


@users_bp.route("", methods=["GET"])
def list_users():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except (ValueError, TypeError):
        return jsonify(error="Bad Request", message="page and per_page must be integers"), 400

    cache_key = f"users:p{page}:pp{per_page}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    offset = (page - 1) * per_page
    users = User.select().order_by(User.id).offset(offset).limit(per_page)
    data = [_user_dict(u) for u in users]
    cache_set(cache_key, data, ttl=10)
    return jsonify(data), 200


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not Found", message=f"User {user_id} not found"), 404
    return jsonify(_user_dict(user)), 200


@users_bp.route("", methods=["POST"])
def create_user():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    email = data.get("email")

    if not isinstance(username, str) or not isinstance(email, str):
        return jsonify(error="Bad Request", message="username and email must be strings"), 400

    try:
        with db.atomic():
            user = User.create(username=username, email=email)
    except IntegrityError:
        return jsonify(error="Conflict", message="username or email already exists"), 409

    return jsonify(_user_dict(user)), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not Found", message=f"User {user_id} not found"), 404

    data = request.get_json(silent=True) or {}

    if "username" in data:
        if not isinstance(data["username"], str):
            return jsonify(error="Bad Request", message="username must be a string"), 400
        user.username = data["username"]

    if "email" in data:
        if not isinstance(data["email"], str):
            return jsonify(error="Bad Request", message="email must be a string"), 400
        user.email = data["email"]

    try:
        with db.atomic():
            user.save()
    except IntegrityError:
        return jsonify(error="Conflict", message="username or email already exists"), 409

    return jsonify(_user_dict(user)), 200

@users_bp.route("/<int:user_id>/urls", methods=["GET"])
def user_urls(user_id):
    from app.models.url import URL
    try:
        user = User.get_by_id(user_id)
        urls = URL.select().where(URL.user == user)
        return jsonify([{
            "short_code": u.short_code,
            "original_url": u.original_url,
            "title": u.title,
            "is_active": u.is_active,
            "created_at": str(u.created_at)
        } for u in urls]), 200
    except User.DoesNotExist:
        return jsonify(error="Not Found", message="User not found"), 404