import json

from flask import Blueprint, jsonify, request

from app.cache import cache_get, cache_set, parse_pagination
from app.models.event import Event

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

    cache_key = f"events:p{page}:pp{per_page}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    offset = (page - 1) * per_page
    events = Event.select().order_by(Event.id).offset(offset).limit(per_page)
    data = [_event_dict(e) for e in events]
    cache_set(cache_key, data, ttl=CACHE_TTL)
    return jsonify(data), 200
