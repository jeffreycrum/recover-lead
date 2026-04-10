import time

import redis.asyncio as redis
import structlog

from app.config import redis_url_with_db, settings
from app.core.exceptions import RateLimitError

logger = structlog.get_logger()

TIER_LIMITS: dict[str, int] = {
    "free": 5,
    "starter": 20,
    "pro": 40,
    "agency": 60,
}

# Rate limit Redis uses db 1
_redis_client: redis.Redis | None = None


def get_rate_limit_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(redis_url_with_db(settings.redis_url, 1))
    return _redis_client


async def check_rate_limit(user_id: str, plan: str = "free") -> dict[str, int]:
    """Check and enforce rate limit for a user. Returns limit headers."""
    r = get_rate_limit_redis()
    limit = TIER_LIMITS.get(plan, TIER_LIMITS["free"])
    window = 60  # 1 minute window

    key = f"rate_limit:{user_id}:{int(time.time()) // window}"

    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    results = await pipe.execute()

    current = results[0]
    remaining = max(0, limit - current)
    reset_at = ((int(time.time()) // window) + 1) * window

    if current > limit:
        raise RateLimitError(retry_after=reset_at - int(time.time()))

    return {
        "X-RateLimit-Limit": limit,
        "X-RateLimit-Remaining": remaining,
        "X-RateLimit-Reset": reset_at,
    }
