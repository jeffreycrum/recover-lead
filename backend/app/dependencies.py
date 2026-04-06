import uuid

import structlog
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import get_clerk_user_id
from app.core.exceptions import ForbiddenError
from app.db.session import get_async_session
from app.models.billing import SkipTraceCredits, Subscription
from app.models.user import User

logger = structlog.get_logger()


async def get_current_user(
    clerk_id: str = Depends(get_clerk_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Get the current authenticated user from the database.

    Auto-creates the user record on first sign-in if the Clerk webhook
    hasn't fired yet (race condition on first login).
    """
    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-provision user on first API call (webhook may not have fired yet)
        # Use a retry loop to handle race conditions from concurrent requests
        try:
            logger.info("auto_provisioning_user", clerk_id=clerk_id)
            user = User(clerk_id=clerk_id, email=f"{clerk_id}@pending.recoverlead.com")
            session.add(user)
            await session.flush()

            session.add(Subscription(user_id=user.id, plan="free", status="active"))
            session.add(SkipTraceCredits(user_id=user.id, credits_remaining=0))
            await session.flush()

            logger.info("user_auto_provisioned", user_id=str(user.id), clerk_id=clerk_id)
        except Exception:
            # Race condition: another request already created this user
            await session.rollback()
            result = await session.execute(select(User).where(User.clerk_id == clerk_id))
            user = result.scalar_one_or_none()
            if not user:
                raise

    if not user.is_active:
        raise ForbiddenError()

    return user


async def get_current_user_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Get just the user ID for simpler dependency injection."""
    return user.id
