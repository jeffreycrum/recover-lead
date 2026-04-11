"""External provider webhooks (Lob, etc)."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.letter import Letter

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# Map Lob event_type IDs to our internal letter status.
_LOB_EVENT_TO_STATUS: dict[str, str] = {
    "letter.mailed": "mailed",
    "letter.in_transit": "in_transit",
    "letter.in_local_area": "in_transit",
    "letter.processed_for_delivery": "in_transit",
    "letter.re_routed": "in_transit",
    "letter.delivered": "delivered",
    "letter.returned_to_sender": "returned",
}


@router.post("/lob")
async def lob_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Handle Lob letter status events.

    Supported events: letter.mailed, letter.in_transit, letter.in_local_area,
    letter.processed_for_delivery, letter.delivered, letter.re_routed,
    letter.returned_to_sender.

    TODO: verify Lob webhook signature before trusting payload (Lob signs
    with HMAC-SHA256 using settings.lob_webhook_secret).
    """
    payload = await request.json()
    event_type = (payload.get("event_type") or {}).get("id", "")
    body = payload.get("body") or {}
    lob_id = body.get("id", "")

    if not lob_id:
        logger.warning("lob_webhook_missing_id", event=event_type)
        return {"status": "ok", "message": "no lob_id"}

    result = await session.execute(select(Letter).where(Letter.lob_id == lob_id))
    letter = result.scalar_one_or_none()
    if not letter:
        logger.warning("lob_webhook_unknown_letter", lob_id=lob_id, event=event_type)
        return {"status": "ok", "message": "unknown letter"}

    new_status = _LOB_EVENT_TO_STATUS.get(event_type)
    if new_status:
        letter.status = new_status
        letter.lob_status = event_type
        if new_status == "delivered":
            letter.delivery_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        elif new_status == "returned":
            letter.return_reason = (body.get("metadata") or {}).get(
                "return_reason", "unknown"
            )
        await session.commit()
        logger.info(
            "lob_webhook_processed",
            lob_id=lob_id,
            event=event_type,
            new_status=new_status,
        )
    else:
        logger.info("lob_webhook_ignored_event", lob_id=lob_id, event=event_type)

    return {"status": "ok"}
