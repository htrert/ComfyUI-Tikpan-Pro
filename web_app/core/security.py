import time
from collections import defaultdict, deque

from flask import request


_attempts = defaultdict(deque)


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(key, limit=10, window_seconds=60):
    """Simple per-process limiter for abuse resistance.

    Production deployments with multiple instances should back this with Redis.
    """
    now = time.time()
    bucket = _attempts[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = int(window_seconds - (now - bucket[0])) if bucket else window_seconds
        return False, max(retry_after, 1)
    bucket.append(now)
    return True, 0
