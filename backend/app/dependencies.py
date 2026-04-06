import uuid

import structlog
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import get_clerk_user_id
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_async_session
from app.models.user import User

logger = structlog.get_logger()


async def get_current_user(
    clerk_id: str = Depends(get_clerk_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Get the current authenticated user from the database."""
    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User")

    if not user.is_active:
        raise ForbiddenError()

    return user


async def get_current_user_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Get just the user ID for simpler dependency injection."""
    return user.id
