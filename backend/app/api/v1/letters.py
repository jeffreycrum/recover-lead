import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientCreditsError, NotFoundError
from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.models.letter import Letter
from app.models.user import User
from app.schemas.lead import CursorPage
from app.schemas.letter import (
    LetterBatchRequest,
    LetterGenerateRequest,
    LetterListResponse,
    LetterResponse,
    LetterUpdateRequest,
)
from app.schemas.letter import (
    MailLetterRequest as MailLetterRequestSchema,
)
from app.services.letter_service import generate_pdf

logger = structlog.get_logger()
router = APIRouter(prefix="/letters", tags=["letters"])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

VALID_LETTER_STATUSES = {
    "draft",
    "approved",
    "mailed",
    "in_transit",
    "delivered",
    "returned",
}

# Allowed state transitions users can trigger via PATCH /letters/{id}.
# Transitions driven by the mailing task / Lob webhook happen separately.
LETTER_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved"},
    "approved": {"draft", "mailed"},
    "mailed": {"in_transit", "delivered", "returned"},
    "in_transit": {"delivered", "returned"},
    "delivered": set(),
    "returned": set(),
}


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_letter(
    req: LetterGenerateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Generate a letter for a lead. Async via Celery task."""
    # Verify lead is claimed by this user
    result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user.id,
            UserLead.lead_id == req.lead_id,
        )
    )
    user_lead = result.scalar_one_or_none()
    if not user_lead:
        raise NotFoundError("Claimed lead")

    from app.services.billing_service import reserve_usage

    reservation = await reserve_usage(session, user.id, "letter", count=1)
    if not reservation.allowed:
        raise InsufficientCreditsError()

    from app.core.sse import register_task_owner
    from app.workers.letter_tasks import generate_letter_task

    task = generate_letter_task.delay(
        str(user.id),
        str(req.lead_id),
        req.letter_type,
        reservation.overage_count > 0,
        reservation.period_start_iso,
    )
    register_task_owner(task.id, str(user.id))

    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Letter generation queued",
    }


MAX_BATCH_SIZE = 100


@router.post("/generate-batch", status_code=status.HTTP_202_ACCEPTED)
async def generate_batch(
    req: LetterBatchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Batch generate letters for multiple leads. Async via Celery."""
    if not req.lead_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_LEADS", "message": "Provide at least one lead_id"},
        )
    if len(req.lead_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BATCH_TOO_LARGE",
                "message": f"Maximum {MAX_BATCH_SIZE} leads per batch",
            },
        )

    from app.services.billing_service import reserve_usage

    reservation = await reserve_usage(session, user.id, "letter", count=len(req.lead_ids))
    if not reservation.allowed:
        raise InsufficientCreditsError()

    from app.core.sse import register_task_owner
    from app.workers.letter_tasks import generate_batch_task

    task = generate_batch_task.delay(
        str(user.id),
        [str(lid) for lid in req.lead_ids],
        req.letter_type,
        reservation.overage_count,
        reservation.period_start_iso,
    )
    register_task_owner(task.id, str(user.id))

    return {
        "task_id": task.id,
        "status": "queued",
        "lead_count": len(req.lead_ids),
        "message": "Batch letter generation queued",
    }


@router.get("", response_model=CursorPage)
async def list_letters(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    letter_status: str | None = Query(None, alias="status"),
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE),
) -> CursorPage:
    """List letters for the current user."""
    query = (
        select(Letter, Lead.case_number, County.name.label("county_name"), Lead.owner_name)
        .join(Lead, Letter.lead_id == Lead.id)
        .join(County, Lead.county_id == County.id)
        .where(Letter.user_id == user.id)
        .order_by(Letter.created_at.desc(), Letter.id)
    )

    if letter_status:
        query = query.where(Letter.status == letter_status)

    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
            cursor_result = await session.execute(
                select(Letter.created_at).where(Letter.id == cursor_uuid)
            )
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time is not None:
                query = query.where(
                    (Letter.created_at < cursor_time)
                    | ((Letter.created_at == cursor_time) & (Letter.id > cursor_uuid))
                )
        except ValueError:
            pass

    query = query.limit(limit + 1)
    result = await session.execute(query)
    rows = result.all()

    has_more = len(rows) > limit
    items = rows[:limit]

    return CursorPage(
        items=[
            LetterListResponse(
                id=ltr.id,
                lead_id=ltr.lead_id,
                letter_type=ltr.letter_type,
                status=ltr.status,
                created_at=ltr.created_at,
                case_number=case_number,
                county_name=county_name,
                owner_name=owner_name,
            )
            for ltr, case_number, county_name, owner_name in items
        ],
        next_cursor=str(items[-1][0].id) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/{letter_id}", response_model=LetterResponse)
async def get_letter(
    letter_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> LetterResponse:
    """Get letter detail."""
    result = await session.execute(
        select(
            Letter,
            Lead.case_number,
            County.name.label("county_name"),
            Lead.owner_name,
            Lead.surplus_amount,
        )
        .join(Lead, Letter.lead_id == Lead.id)
        .join(County, Lead.county_id == County.id)
        .where(Letter.id == letter_id, Letter.user_id == user.id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Letter")

    ltr, case_number, county_name, owner_name, surplus_amount = row

    return LetterResponse(
        id=ltr.id,
        lead_id=ltr.lead_id,
        letter_type=ltr.letter_type,
        content=ltr.content,
        status=ltr.status,
        sent_at=ltr.sent_at,
        created_at=ltr.created_at,
        case_number=case_number,
        county_name=county_name,
        owner_name=owner_name,
        surplus_amount=float(surplus_amount),
        lob_id=ltr.lob_id,
        lob_status=ltr.lob_status,
        mailed_at=ltr.mailed_at,
        tracking_url=ltr.tracking_url,
        expected_delivery_date=ltr.expected_delivery_date,
    )


@router.patch("/{letter_id}", response_model=LetterResponse)
async def update_letter(
    letter_id: uuid.UUID,
    req: LetterUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> LetterResponse:
    """Edit letter content or approve it."""
    result = await session.execute(
        select(Letter).where(Letter.id == letter_id, Letter.user_id == user.id)
    )
    ltr = result.scalar_one_or_none()
    if not ltr:
        raise NotFoundError("Letter")

    # Content edits are only allowed while the letter is a draft.
    if req.content is not None:
        if ltr.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "NOT_EDITABLE",
                    "message": "Only draft letters can be edited",
                },
            )
        ltr.content = req.content

    if req.status is not None:
        if req.status not in VALID_LETTER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_STATUS",
                    "message": f"Status must be one of {sorted(VALID_LETTER_STATUSES)}",
                },
            )
        allowed = LETTER_STATUS_TRANSITIONS.get(ltr.status, set())
        if req.status != ltr.status and req.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_TRANSITION",
                    "message": (
                        f"Cannot transition letter from {ltr.status} to {req.status}"
                    ),
                },
            )
        ltr.status = req.status

    await session.flush()

    # Re-fetch with joins for response
    result = await session.execute(
        select(Lead.case_number, County.name, Lead.owner_name, Lead.surplus_amount)
        .join(County, Lead.county_id == County.id)
        .where(Lead.id == ltr.lead_id)
    )
    lead_row = result.one_or_none()
    case_number, county_name, owner_name, surplus_amount = (
        lead_row if lead_row else (None, None, None, None)
    )

    return LetterResponse(
        id=ltr.id,
        lead_id=ltr.lead_id,
        letter_type=ltr.letter_type,
        content=ltr.content,
        status=ltr.status,
        sent_at=ltr.sent_at,
        created_at=ltr.created_at,
        case_number=case_number,
        county_name=county_name,
        owner_name=owner_name,
        surplus_amount=float(surplus_amount) if surplus_amount else None,
        lob_id=ltr.lob_id,
        lob_status=ltr.lob_status,
        mailed_at=ltr.mailed_at,
        tracking_url=ltr.tracking_url,
        expected_delivery_date=ltr.expected_delivery_date,
    )


@router.delete("/{letter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_letter(
    letter_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a draft letter."""
    result = await session.execute(
        select(Letter).where(Letter.id == letter_id, Letter.user_id == user.id)
    )
    ltr = result.scalar_one_or_none()
    if not ltr:
        raise NotFoundError("Letter")

    if ltr.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NOT_DELETABLE", "message": "Only draft letters can be deleted"},
        )

    await session.delete(ltr)


@router.get("/{letter_id}/pdf")
async def download_pdf(
    letter_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Download letter as PDF."""
    result = await session.execute(
        select(Letter, Lead.case_number)
        .join(Lead, Letter.lead_id == Lead.id)
        .where(Letter.id == letter_id, Letter.user_id == user.id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Letter")

    ltr, case_number = row
    pdf_bytes = generate_pdf(ltr.content, case_number or "")

    filename = f"letter_{case_number or ltr.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{letter_id}/mail", status_code=status.HTTP_202_ACCEPTED)
async def mail_letter(
    letter_id: uuid.UUID,
    req: MailLetterRequestSchema,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Queue an approved letter for physical mailing via Lob.

    Reserves a mailing slot against the user's plan, then dispatches a
    Celery task that calls Lob and updates the letter status to "mailed".
    """
    result = await session.execute(
        select(Letter).where(Letter.id == letter_id, Letter.user_id == user.id)
    )
    ltr = result.scalar_one_or_none()
    if not ltr:
        raise NotFoundError("Letter")

    if ltr.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NOT_MAILABLE",
                "message": "Only approved letters can be mailed",
            },
        )

    from app.services.billing_service import reserve_usage

    reservation = await reserve_usage(session, user.id, "mailing", count=1)
    if not reservation.allowed:
        raise InsufficientCreditsError()

    from_address = {
        "name": req.from_name,
        "street1": req.from_street1,
        "street2": req.from_street2 or "",
        "city": req.from_city,
        "state": req.from_state,
        "zip_code": req.from_zip,
        "country": "US",
    }
    to_address = {
        "name": req.to_name,
        "street1": req.to_street1,
        "street2": req.to_street2 or "",
        "city": req.to_city,
        "state": req.to_state,
        "zip_code": req.to_zip,
        "country": "US",
    }

    from app.core.sse import register_task_owner
    from app.workers.mailing_tasks import mail_letter_via_lob

    task = mail_letter_via_lob.delay(
        str(letter_id),
        str(user.id),
        from_address,
        to_address,
        reservation.overage_count > 0,
        reservation.period_start_iso,
    )
    register_task_owner(task.id, str(user.id))

    logger.info(
        "letter_mail_queued",
        letter_id=str(letter_id),
        user_id=str(user.id),
        is_overage=reservation.overage_count > 0,
    )

    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Letter queued for mailing",
    }
