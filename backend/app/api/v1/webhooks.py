"""External provider webhooks (Lob, etc)."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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

# Whitelist of known Lob return reason strings. Anything else -> "unknown"
# to prevent stored XSS via unauthenticated/unsanitized webhook payloads.
_VALID_RETURN_REASONS = {
    "insufficient_address",
    "undeliverable",
    "refused",
    "unknown",
    "no_such_number",
    "forwarding_expired",
    "vacant",
    "unclaimed",
    "moved",
}


def _verify_lob_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Lob's HMAC-SHA256 webhook signature.

    Lob sends the signature in the `lob-signature` header. Uses
    constant-time comparison to prevent timing attacks.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/lob")
async def lob_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Handle Lob letter status events.

    Supported events: letter.mailed, letter.in_transit, letter.in_local_area,
    letter.processed_for_delivery, letter.delivered, letter.re_routed,
    letter.returned_to_sender.
    """
    # Read the raw body so we can compute the HMAC signature before parsing.
    raw_body = await request.body()

    # Verify signature — rejects any unauthenticated/forged event.
    signature = request.headers.get("lob-signature", "")
    if not _verify_lob_signature(raw_body, signature, settings.lob_webhook_secret):
        logger.warning("lob_webhook_invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_SIGNATURE", "message": "Unauthorized"},
        )

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_JSON", "message": "Malformed webhook payload"},
        ) from None

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
            raw_reason = (body.get("metadata") or {}).get("return_reason", "unknown")
            # Whitelist known values; anything else -> "unknown"
            letter.return_reason = (
                raw_reason if raw_reason in _VALID_RETURN_REASONS else "unknown"
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
