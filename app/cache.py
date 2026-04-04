import json
import os

import redis

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
