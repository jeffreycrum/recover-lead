import json

import redis.asyncio as redis
import structlog
from fastapi import Request

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


async def cache_response(idempotency_key: str, status_code: int, body: dict) -> None:
    """Cache a response for an idempotency key."""
    r = get_idempotency_redis()
    data = json.dumps({"status_code": status_code, "body": body})
    await r.setex(f"idempotency:{idempotency_key}", IDEMPOTENCY_TTL, data)


async def claim_idempotency_key(idempotency_key: str, processing_ttl: int = 30) -> bool:
    """Atomically claim a key as in-progress using SET NX.

    Returns True if this caller is the sole processor.
    Returns False if another request already holds the lock.
    The lock TTL is short (30 s) so a crash doesn't block the key forever;
    the full IDEMPOTENCY_TTL applies only after the response is stored.
    """
    r = get_idempotency_redis()
    result = await r.set(
        f"idempotency:lock:{idempotency_key}", "processing", ex=processing_ttl, nx=True
    )
    return result is not None


async def release_idempotency_key(idempotency_key: str) -> None:
    """Release an in-progress idempotency lock.

    Call this when a request fails after claiming the lock so that retries
    receive the real error response rather than a 409 conflict.
    """
    r = get_idempotency_redis()
    await r.delete(f"idempotency:lock:{idempotency_key}")


def get_idempotency_key(request: Request) -> str | None:
    """Extract idempotency key from request headers."""
    return request.headers.get("Idempotency-Key")
