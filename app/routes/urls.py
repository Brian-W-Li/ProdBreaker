# type: ignore
import random
import string
import json
from datetime import datetime
from flask import Blueprint, jsonify, request, redirect
from app.models.url import URL
from app.models.event import Event
from app.models.user import User

urls_bp = Blueprint("urls", __name__)


def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


@urls_bp.route("/shorten", methods=["POST"])
def shorten_url():
    data = request.get_json()

    if not data or not data.get("url"):
        return jsonify(error="Missing 'url' field"), 400

    original_url = data["url"]
    if not original_url.startswith(("http://", "https://")):
        return jsonify(error="URL must start with http:// or https://"), 400

    title = data.get("title")
    user_id = data.get("user_id")

    if not user_id:
        return jsonify(error="Missing 'user_id' field"), 400

    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    for _ in range(5):
        code = generate_short_code()
        if not URL.select().where(URL.short_code == code).exists():
            break
    else:
        return jsonify(error="Could not generate unique code, try again"), 500

    url = URL.create(
        user=user,
        short_code=code,
        original_url=original_url,
        title=title,
    )

    Event.create(
        url=url,
        user=user,
        event_type="created",
        details=json.dumps({"short_code": code, "original_url": original_url})
    )

    return jsonify(short_code=url.short_code, url=f"/{url.short_code}"), 201


@urls_bp.route("/<short_code>", methods=["GET"])
def redirect_url(short_code):
    try:
        url = URL.get(URL.short_code == short_code)
    except URL.DoesNotExist:
        return jsonify(error="Short code not found"), 404

    if not url.is_active:
        return jsonify(error="This link has been deactivated"), 410

    Event.create(
        url=url,
        user=url.user,
        event_type="clicked",
        details=json.dumps({"short_code": short_code})
    )

    return redirect(url.original_url)


@urls_bp.route("/stats/<short_code>", methods=["GET"])
def url_stats(short_code):
    try:
        url = URL.get(URL.short_code == short_code)
    except URL.DoesNotExist:
        return jsonify(error="Short code not found"), 404

    clicks = Event.select().where(
        Event.url == url,
        Event.event_type == "clicked"
    ).count()

    return jsonify(
        short_code=url.short_code,
        original_url=url.original_url,
        title=url.title,
        clicks=clicks,
        created_at=str(url.created_at),
        is_active=url.is_active
    )


@urls_bp.route("/urls/<short_code>", methods=["DELETE"])
def deactivate_url(short_code):
    try:
        url = URL.get(URL.short_code == short_code)
    except URL.DoesNotExist:
        return jsonify(error="Short code not found"), 404

    url.is_active = False
    url.updated_at = datetime.now()
    url.save()

    Event.create(
        url=url,
        user=url.user,
        event_type="deactivated",
        details=json.dumps({"short_code": short_code})
    )

    return jsonify(message="URL deactivated"), 200