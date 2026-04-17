from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def ensure_asyncpg_url(url: str) -> str:
    """Convert postgresql:// to postgresql+asyncpg:// for SQLAlchemy async."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    ensure_asyncpg_url(settings.database_url),
    pool_size=5,
    max_overflow=10,
    echo=not settings.is_production,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def make_worker_session() -> AsyncSession:
    """Create a session backed by NullPool for Celery tasks.

    Each Celery prefork task runs in its own asyncio event loop. asyncpg
    connections are loop-bound, so a pooled connection from a previous task's
    loop raises InterfaceError on reuse. NullPool never reuses connections,
    giving each task a fresh connection that is closed on session exit.
    """
    worker_engine = create_async_engine(
        ensure_asyncpg_url(settings.database_url),
        poolclass=NullPool,
    )
    factory = async_sessionmaker(worker_engine, class_=AsyncSession, expire_on_commit=False)
    return factory()
