# type: ignore
import json
import random
import string
from datetime import datetime

from flask import Blueprint, jsonify, redirect, request
from peewee import IntegrityError

from app.cache import cache_get, cache_set, bump_generation, GEN_URLS, parse_pagination
from app.database import db, log_event_async
from app.models.url import Url
from app.models.user import User

urls_bp = Blueprint("urls", __name__, url_prefix="/urls")
redirect_bp = Blueprint("redirect", __name__)


def _generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def _url_dict(url):
    return {
        "id": url.id,
        "user_id": url.user_id,
        "short_code": url.short_code,
        "original_url": url.original_url,
        "title": url.title,
        "is_active": url.is_active,
        "created_at": url.created_at.isoformat() if url.created_at else None,
        "updated_at": url.updated_at.isoformat() if url.updated_at else None,
    }


@urls_bp.route("", methods=["POST"])
def create_url():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    original_url = data.get("original_url")
    title = data.get("title")

    if not user_id or not original_url:
        return jsonify(error="Bad Request", message="user_id and original_url are required"), 400

    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not Found", message=f"User {user_id} not found"), 404

    url = None
    for _ in range(10):
        try:
            short_code = _generate_short_code()
            with db.atomic():
                url = Url.create(
                    user=user,
                    short_code=short_code,
                    original_url=original_url,
                    title=title,
                )
            log_event_async(url.id, user.id, 'created',
                            json.dumps({"short_code": short_code, "original_url": original_url}))
            break
        except IntegrityError:
            continue

    if url is None:
        return jsonify(error="Internal Server Error", message="Could not generate unique short code"), 500

    bump_generation(GEN_URLS)
    return jsonify(_url_dict(url)), 201


@urls_bp.route("", methods=["GET"])
def list_urls():
    user_id = request.args.get("user_id")
    try:
        page, per_page = parse_pagination(request.args)
    except (ValueError, TypeError):
        return jsonify(error="Bad Request", message="page and per_page must be integers"), 400

    cache_key = f"urls:uid{user_id}:p{page}:pp{per_page}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    query = Url.select()
    if user_id is not None:
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify(error="Bad Request", message="user_id must be an integer"), 400
        query = query.where(Url.user_id == user_id)

    offset = (page - 1) * per_page
    urls = query.order_by(Url.id).offset(offset).limit(per_page)
    data = [_url_dict(u) for u in urls]
    cache_set(cache_key, data, ttl=2)
    return jsonify(data), 200


@urls_bp.route("/<int:url_id>", methods=["GET"])
def get_url(url_id):
    cache_key = f"url:{url_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Not Found", message=f"URL {url_id} not found"), 404
    data = _url_dict(url)
    cache_set(cache_key, data, ttl=30)
    return jsonify(data), 200


@urls_bp.route("/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Not Found", message=f"URL {url_id} not found"), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        url.title = data["title"]

    if "is_active" in data:
        url.is_active = data["is_active"]

    if "original_url" in data:
        url.original_url = data["original_url"]

    url.updated_at = datetime.utcnow()

    with db.atomic():
        url.save(only=[Url.title, Url.is_active, Url.original_url, Url.updated_at])
    log_event_async(url.id, url.user_id, 'updated',
                    json.dumps({"short_code": url.short_code, "original_url": url.original_url}))

    result = _url_dict(url)
    cache_set(f"url:{url_id}", result, ttl=30)
    bump_generation(GEN_URLS)
    return jsonify(result), 200


@urls_bp.route("/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Not Found", message=f"URL {url_id} not found"), 404

    with db.atomic():
        url.delete_instance()

    bump_generation(GEN_URLS)
    return "", 204


@redirect_bp.route("/<short_code>")
def redirect_url(short_code):
    try:
        url = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        return jsonify(error="Not Found", message=f"Short code '{short_code}' not found"), 404

    if not url.is_active:
        return jsonify(error="Gone", message="This shortened URL has been deactivated"), 410

    log_event_async(url.id, url.user_id, 'clicked',
                    json.dumps({"short_code": short_code, "original_url": url.original_url}))
    return redirect(url.original_url, code=302)
