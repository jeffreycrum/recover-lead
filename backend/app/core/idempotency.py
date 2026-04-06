import json

import redis.asyncio as redis
import structlog
from fastapi import Request, Response

from app.config import settings

logger = structlog.get_logger()

IDEMPOTENCY_TTL = 86400  # 24 hours

# Idempotency uses the same Redis as cache (db 0)
_redis_client: redis.Redis | None = None


def get_idempotency_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


async def get_cached_response(idempotency_key: str) -> dict | None:
    """Check if a response is cached for this idempotency key."""
    r = get_idempotency_redis()
    cached = await r.get(f"idempotency:{idempotency_key}")
    if cached:
        logger.info("idempotency_cache_hit", key=idempotency_key)
        return json.loads(cached)
    return None


async def cache_response(
    idempotency_key: str, status_code: int, body: dict
) -> None:
    """Cache a response for an idempotency key."""
    r = get_idempotency_redis()
    data = json.dumps({"status_code": status_code, "body": body})
    await r.setex(f"idempotency:{idempotency_key}", IDEMPOTENCY_TTL, data)


def get_idempotency_key(request: Request) -> str | None:
    """Extract idempotency key from request headers."""
    return request.headers.get("Idempotency-Key")
