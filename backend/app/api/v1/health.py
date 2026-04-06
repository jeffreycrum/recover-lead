import redis.asyncio as redis
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_async_session

logger = structlog.get_logger()
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Liveness probe — is the process running?"""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(session: AsyncSession = Depends(get_async_session)) -> dict[str, str]:
    """Readiness probe — can we reach Postgres and Redis?"""
    checks: dict[str, str] = {}

    # Check Postgres
    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        logger.error("readiness_postgres_failed", error=str(e))
        checks["postgres"] = "error"

    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error("readiness_redis_failed", error=str(e))
        checks["redis"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, **checks}
