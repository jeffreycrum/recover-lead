import uuid
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.county import County
from app.models.lead import Lead, LeadContact, UserLead
from app.models.user import User
from app.schemas.lead import (
    ClaimResponse,
    CursorPage,
    LeadBrowseResponse,
    LeadContactResponse,
    LeadDetailResponse,
    LeadUpdateRequest,
    MyLeadResponse,
    UserLeadResponse,
)
from app.services.lead_service import (
    claim_lead,
    release_lead,
    validate_priority,
    validate_status_transition,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/leads", tags=["leads"])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


@router.get("", response_model=CursorPage)
async def browse_leads(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    county_id: uuid.UUID | None = Query(None),
    surplus_min: Decimal | None = Query(None),
    surplus_max: Decimal | None = Query(None),
    sale_type: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE),
) -> CursorPage:
    """Browse all available leads with filters."""
    query = (
        select(Lead, County.name.label("county_name"))
        .join(County, Lead.county_id == County.id)
        .where(Lead.archived_at.is_(None))
        .order_by(Lead.surplus_amount.desc(), Lead.id)
    )

    if county_id:
        query = query.where(Lead.county_id == county_id)
    if surplus_min is not None:
        query = query.where(Lead.surplus_amount >= surplus_min)
    if surplus_max is not None:
        query = query.where(Lead.surplus_amount <= surplus_max)
    if sale_type:
        query = query.where(Lead.sale_type == sale_type)

    # Cursor pagination (cursor is the last lead ID)
    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
            # Get the surplus_amount of the cursor lead for keyset pagination
            cursor_result = await session.execute(
                select(Lead.surplus_amount).where(Lead.id == cursor_uuid)
            )
            cursor_amount = cursor_result.scalar_one_or_none()
            if cursor_amount is not None:
                query = query.where(
                    (Lead.surplus_amount < cursor_amount)
                    | ((Lead.surplus_amount == cursor_amount) & (Lead.id > cursor_uuid))
                )
        except ValueError:
            pass

    query = query.limit(limit + 1)  # Fetch one extra to check has_more
    result = await session.execute(query)
    rows = result.all()

    has_more = len(rows) > limit
    items = rows[:limit]

    return CursorPage(
        items=[
            LeadBrowseResponse(
                id=lead.id,
                county_name=county_name,
                case_number=lead.case_number,
                property_address=lead.property_address,
                property_city=lead.property_city,
                property_state=lead.property_state,
                surplus_amount=lead.surplus_amount,
                sale_date=lead.sale_date,
                sale_type=lead.sale_type,
                owner_name=lead.owner_name,
                created_at=lead.created_at,
            )
            for lead, county_name in items
        ],
        next_cursor=str(items[-1][0].id) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/mine", response_model=CursorPage)
async def my_leads(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    lead_status: str | None = Query(None, alias="status"),
    min_score: int | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE),
) -> CursorPage:
    """List leads claimed by the current user with pipeline status."""
    query = (
        select(UserLead, Lead, County.name.label("county_name"))
        .join(Lead, UserLead.lead_id == Lead.id)
        .join(County, Lead.county_id == County.id)
        .where(UserLead.user_id == user.id)
        .order_by(UserLead.created_at.desc(), UserLead.id)
    )

    if lead_status:
        query = query.where(UserLead.status == lead_status)
    if min_score is not None:
        query = query.where(UserLead.quality_score >= min_score)

    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
            cursor_result = await session.execute(
                select(UserLead.created_at).where(UserLead.id == cursor_uuid)
            )
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time is not None:
                query = query.where(
                    (UserLead.created_at < cursor_time)
                    | ((UserLead.created_at == cursor_time) & (UserLead.id > cursor_uuid))
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
            MyLeadResponse(
                id=ul.id,
                lead_id=lead.id,
                status=ul.status,
                quality_score=ul.quality_score,
                priority=ul.priority,
                created_at=ul.created_at,
                county_name=county_name,
                case_number=lead.case_number,
                property_address=lead.property_address,
                property_city=lead.property_city,
                surplus_amount=lead.surplus_amount,
                sale_date=lead.sale_date,
                owner_name=lead.owner_name,
            )
            for ul, lead, county_name in items
        ],
        next_cursor=str(items[-1][0].id) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> LeadDetailResponse:
    """Get lead detail with contacts and user-specific state."""
    result = await session.execute(
        select(Lead, County.name.label("county_name"))
        .join(County, Lead.county_id == County.id)
        .where(Lead.id == lead_id)
        .options(selectinload(Lead.contacts))
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Lead")

    lead, county_name = row

    # Get user-specific state (if claimed)
    ul_result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user.id,
            UserLead.lead_id == lead_id,
        )
    )
    user_lead = ul_result.scalar_one_or_none()

    return LeadDetailResponse(
        id=lead.id,
        county_id=lead.county_id,
        county_name=county_name,
        case_number=lead.case_number,
        parcel_id=lead.parcel_id,
        property_address=lead.property_address,
        property_city=lead.property_city,
        property_state=lead.property_state,
        property_zip=lead.property_zip,
        surplus_amount=lead.surplus_amount,
        sale_date=lead.sale_date,
        sale_type=lead.sale_type,
        owner_name=lead.owner_name,
        owner_last_known_address=lead.owner_last_known_address,
        contacts=[
            LeadContactResponse(
                id=c.id,
                contact_type=c.contact_type,
                contact_value=c.contact_value,
                source=c.source,
                confidence=c.confidence,
                is_verified=c.is_verified,
            )
            for c in lead.contacts
        ],
        user_lead=(
            UserLeadResponse(
                id=user_lead.id,
                status=user_lead.status,
                quality_score=user_lead.quality_score,
                quality_reasoning=user_lead.quality_reasoning,
                priority=user_lead.priority,
                created_at=user_lead.created_at,
                updated_at=user_lead.updated_at,
            )
            if user_lead
            else None
        ),
    )


@router.post("/{lead_id}/claim", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def claim(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> ClaimResponse:
    """Claim a lead for your pipeline."""
    user_lead = await claim_lead(session, user.id, lead_id)
    return ClaimResponse(
        user_lead_id=user_lead.id,
        lead_id=lead_id,
        status=user_lead.status,
    )


@router.post("/{lead_id}/release", status_code=status.HTTP_204_NO_CONTENT)
async def release(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> None:
    """Release a claimed lead from your pipeline."""
    await release_lead(session, user.id, lead_id)


@router.patch("/{lead_id}", response_model=UserLeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    req: LeadUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> UserLeadResponse:
    """Update pipeline status or priority for a claimed lead."""
    # Must be claimed by this user
    result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user.id,
            UserLead.lead_id == lead_id,
        )
    )
    user_lead = result.scalar_one_or_none()
    if not user_lead:
        raise NotFoundError("Claimed lead")

    if req.status is not None:
        validate_status_transition(user_lead.status, req.status)
        user_lead.status = req.status

    if req.priority is not None:
        validate_priority(req.priority)
        user_lead.priority = req.priority

    await session.flush()

    return UserLeadResponse(
        id=user_lead.id,
        status=user_lead.status,
        quality_score=user_lead.quality_score,
        quality_reasoning=user_lead.quality_reasoning,
        priority=user_lead.priority,
        created_at=user_lead.created_at,
        updated_at=user_lead.updated_at,
    )


@router.post("/{lead_id}/qualify", status_code=status.HTTP_202_ACCEPTED)
async def qualify_lead_endpoint(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Trigger AI qualification for a lead. Returns task_id for polling."""
    # Must be claimed
    result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user.id,
            UserLead.lead_id == lead_id,
        )
    )
    user_lead = result.scalar_one_or_none()
    if not user_lead:
        raise NotFoundError("Claimed lead")

    from app.workers.qualification_tasks import qualify_single
    task = qualify_single.delay(str(user.id), str(lead_id))

    return {"task_id": task.id, "status": "queued", "message": "Qualification queued"}


@router.post("/bulk-qualify", status_code=status.HTTP_202_ACCEPTED)
async def bulk_qualify(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    lead_ids: list[uuid.UUID] = [],
) -> dict:
    """Trigger AI qualification for multiple leads. Returns task_id."""
    if not lead_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_LEADS", "message": "Provide at least one lead_id"},
        )

    from app.workers.qualification_tasks import qualify_batch
    task = qualify_batch.delay(str(user.id), [str(lid) for lid in lead_ids])

    return {
        "task_id": task.id,
        "status": "queued",
        "lead_count": len(lead_ids),
        "message": "Bulk qualification queued",
    }


@router.post("/{lead_id}/skip-trace", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def skip_trace(
    lead_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> dict:
    """Run skip trace for a lead. Coming soon."""
    return {"message": "Skip trace coming soon"}
