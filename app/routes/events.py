import json

from flask import Blueprint, jsonify, request

from app.cache import cache_get, cache_set, parse_pagination
from app.database import db
from app.models.event import Event
from app.models.url import Url
from app.models.user import User

events_bp = Blueprint("events", __name__, url_prefix="/events")

CACHE_TTL = 10


def _event_dict(event):
    details = event.details
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except (ValueError, TypeError):
            details = {}
    return {
        "id": event.id,
        "url_id": event.url_id,
        "user_id": event.user_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "details": details,
    }


@events_bp.route("", methods=["GET"])
def list_events():
    try:
        page, per_page = parse_pagination(request.args)
    except (ValueError, TypeError):
        return jsonify(error="Bad Request", message="page and per_page must be integers"), 400

    url_id = request.args.get("url_id")
    user_id = request.args.get("user_id")
    event_type = request.args.get("event_type")

    if url_id is not None:
        try:
            url_id = int(url_id)
        except (ValueError, TypeError):
            return jsonify(error="Bad Request", message="url_id must be an integer"), 400

    if user_id is not None:
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify(error="Bad Request", message="user_id must be an integer"), 400

    cache_key = f"events:uid{url_id}:userid{user_id}:type{event_type}:p{page}:pp{per_page}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    query = Event.select()
    if url_id is not None:
        query = query.where(Event.url_id == url_id)
    if user_id is not None:
        query = query.where(Event.user_id == user_id)
    if event_type is not None:
        query = query.where(Event.event_type == event_type)

    offset = (page - 1) * per_page
    events = query.order_by(Event.id).offset(offset).limit(per_page)
    data = [_event_dict(e) for e in events]
    cache_set(cache_key, data, ttl=CACHE_TTL)
    return jsonify(data), 200


@events_bp.route("", methods=["POST"])
def create_event():
    data = request.get_json(silent=True) or {}

    url_id = data.get("url_id")
    user_id = data.get("user_id")
    event_type = data.get("event_type")
    details = data.get("details", {})

    if not url_id or not user_id or not event_type:
        return jsonify(error="Bad Request", message="url_id, user_id, and event_type are required"), 400

    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="Not Found", message=f"URL {url_id} not found"), 404

    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not Found", message=f"User {user_id} not found"), 404

    with db.atomic():
        event = Event.create(
            url=url,
            user=user,
            event_type=event_type,
            details=json.dumps(details) if isinstance(details, dict) else details,
        )

    return jsonify(_event_dict(event)), 201


@events_bp.route("/<int:event_id>", methods=["GET"])
def get_event(event_id):
    cache_key = f"event:{event_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return jsonify(error="Not Found", message=f"Event {event_id} not found"), 404

    data = _event_dict(event)
    cache_set(cache_key, data, ttl=CACHE_TTL)
    return jsonify(data), 200
