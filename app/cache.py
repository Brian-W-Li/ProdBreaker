import json
import os

import redis

GEN_USERS = "gen:users"
GEN_URLS = "gen:urls"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return _client


def cache_get(key):
    try:
        value = get_client().get(key)
        return json.loads(value) if value is not None else None
    except redis.RedisError:
        return None


def cache_set(key, value, ttl=60):
    try:
        get_client().setex(key, ttl, json.dumps(value))
    except redis.RedisError:
        pass


def get_generation(gen_key):
    try:
        val = get_client().get(gen_key)
        return val if val is not None else "0"
    except redis.RedisError:
        return "0"


def get_generations(*gen_keys):
    """Fetch multiple generation counters in one Redis round trip."""
    try:
        pipe = get_client().pipeline(transaction=False)
        for key in gen_keys:
            pipe.get(key)
        results = pipe.execute()
        return [v or "0" for v in results]
    except redis.RedisError:
        return ["0"] * len(gen_keys)


def bump_generation(gen_key):
    try:
        get_client().incr(gen_key)
    except redis.RedisError:
        pass


def parse_pagination(request_args):
    """Parse and clamp page/per_page from query string. Raises ValueError on bad input."""
    page = max(1, int(request_args.get("page", 1)))
    per_page = min(100, max(1, int(request_args.get("per_page", 20))))
    return page, per_page
