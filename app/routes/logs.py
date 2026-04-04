import json

from flask import Blueprint, jsonify, request

from app.logging_config import LOG_FILE

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs")
def get_logs():
    try:
        lines = min(int(request.args.get("lines", 100)), 1000)
    except (TypeError, ValueError):
        lines = 100

    try:
        with open(LOG_FILE) as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        return jsonify([])

    entries = []
    for line in raw_lines[-lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"message": line})

    return jsonify(entries)
