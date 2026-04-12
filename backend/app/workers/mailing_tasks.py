"""Celery tasks for physical letter mailing via Lob."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.engine import ensure_asyncpg_url
from app.models.letter import Letter
from app.services.billing_service import (
    record_overage_usage,
    release_reservation,
)
from app.services.mailing import Address, MailLetterRequest
from app.services.mailing.factory import get_mailing_provider
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


def _get_worker_session() -> AsyncSession:
    engine = create_async_engine(
        ensure_asyncpg_url(settings.database_url), pool_size=2, max_overflow=0
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


def _naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@celery_app.task(
    name="app.workers.mailing_tasks.mail_letter_via_lob",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def mail_letter_via_lob(
    self,
    letter_id: str,
    user_id: str,
    from_address: dict,
    to_address: dict,
    is_overage: bool,
    period_start_iso: str,
) -> dict:
    """Mail an approved letter via Lob and update the letter row."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _mail_letter(
                letter_id,
                user_id,
                from_address,
                to_address,
                is_overage,
                period_start_iso,
            )
        )
    finally:
        loop.close()


async def _mail_letter(
    letter_id: str,
    user_id: str,
    from_address: dict,
    to_address: dict,
    is_overage: bool,
    period_start_iso: str,
) -> dict:
    user_uuid = uuid.UUID(user_id)
    period = period_start_iso or None

    # Reservation MUST be released on every exit path (success or failure).
    # Use try/finally so a post-send DB commit error doesn't leave a
    # phantom reservation that locks the user out of future mailings.
    reservation_released = False

    try:
        async with _get_worker_session() as session:
            result = await session.execute(
                select(Letter)
                .options(selectinload(Letter.lead))
                .where(
                    Letter.id == uuid.UUID(letter_id),
                    Letter.user_id == user_uuid,
                )
            )
            letter = result.scalar_one_or_none()
            if not letter:
                logger.warning("mail_letter_not_found", letter_id=letter_id)
                return {"error": "letter not found"}

            if letter.status != "approved":
                logger.warning(
                    "mail_letter_wrong_state",
                    letter_id=letter_id,
                    status=letter.status,
                )
                return {"error": f"letter not in approved state: {letter.status}"}

            case_number = letter.lead.case_number if letter.lead else letter_id

            provider = get_mailing_provider()
            try:
                mail_result = provider.send_letter(
                    MailLetterRequest(
                        to_address=Address(**to_address),
                        from_address=Address(**from_address),
                        content_html=letter.content,
                        description=(
                            f"RecoverLead surplus claim — case {case_number}"
                        ),
                    )
                )
            except Exception as e:
                logger.error(
                    "mail_letter_provider_exception",
                    letter_id=letter_id,
                    error=str(e),
                )
                raise

            if not mail_result.success:
                logger.error(
                    "mail_letter_provider_error",
                    letter_id=letter_id,
                    error=mail_result.error,
                )
                return {"error": mail_result.error}

            # Success — update letter state
            letter.status = "mailed"
            letter.lob_id = mail_result.provider_id
            letter.lob_status = "created"
            letter.mailed_at = _naive_utc_now()
            letter.tracking_url = mail_result.tracking_url or None
            letter.mailing_address_to = _serialize_address(to_address)
            letter.mailing_address_from = _serialize_address(from_address)
            if mail_result.expected_delivery_date:
                try:
                    letter.expected_delivery_date = date.fromisoformat(
                        mail_result.expected_delivery_date[:10]
                    )
                except (ValueError, TypeError):
                    pass

            await session.commit()
            if is_overage:
                await record_overage_usage(session, user_uuid, "mailing")

            logger.info(
                "letter_mailed",
                letter_id=letter_id,
                lob_id=mail_result.provider_id,
            )
            return {"success": True, "lob_id": mail_result.provider_id}
    finally:
        if not reservation_released:
            release_reservation(user_uuid, "mailing", 1, period)
            reservation_released = True


def _serialize_address(addr: dict) -> str:
    """Serialize an address dict to a single-line string for encrypted storage."""
    parts = [
        addr.get("name", ""),
        addr.get("street1", ""),
        addr.get("street2", ""),
        f"{addr.get('city', '')}, {addr.get('state', '')} {addr.get('zip_code', '')}".strip(),
        addr.get("country", "US"),
    ]
    return " | ".join(p for p in parts if p)
