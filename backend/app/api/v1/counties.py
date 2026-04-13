import uuid

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.county import County
from app.models.lead import Lead
from app.models.user import User

logger = structlog.get_logger()
router = APIRouter(prefix="/counties", tags=["counties"])


@router.get("")
async def list_counties(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    state: str | None = Query(None),
    active_only: bool = Query(False),
) -> list[dict]:
    """List all counties with lead counts. Includes inactive counties with contact info."""
    query = (
        select(
            County,
            func.count(Lead.id).label("lead_count"),
        )
        .outerjoin(Lead, (Lead.county_id == County.id) & Lead.archived_at.is_(None))
        .group_by(County.id)
        .order_by(County.state, County.name)
    )

    if state:
        query = query.where(County.state == state.upper())
    if active_only:
        query = query.where(County.is_active.is_(True))

    result = await session.execute(query)
    rows = result.all()

    return [
        {
            "id": str(county.id),
            "name": county.name,
            "state": county.state,
            "fips_code": county.fips_code,
            "source_type": county.source_type,
            "source_url": county.source_url,
            "is_active": county.is_active,
            "contact_phone": county.contact_phone,
            "contact_email": county.contact_email,
            "last_scraped_at": county.last_scraped_at.isoformat()
            if county.last_scraped_at
            else None,
            "lead_count": lead_count,
        }
        for county, lead_count in rows
    ]


@router.get("/{county_id}")
async def get_county(
    county_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Get county details."""
    result = await session.execute(select(County).where(County.id == county_id))
    county = result.scalar_one_or_none()
    if not county:
        raise NotFoundError("County")

    # Get lead count
    result = await session.execute(
        select(func.count())
        .select_from(Lead)
        .where(
            Lead.county_id == county_id,
            Lead.archived_at.is_(None),
        )
    )
    lead_count = result.scalar() or 0

    return {
        "id": str(county.id),
        "name": county.name,
        "state": county.state,
        "fips_code": county.fips_code,
        "source_url": county.source_url,
        "source_type": county.source_type,
        "is_active": county.is_active,
        "contact_phone": county.contact_phone,
        "contact_email": county.contact_email,
        "last_scraped_at": county.last_scraped_at.isoformat() if county.last_scraped_at else None,
        "lead_count": lead_count,
    }


@router.post("/{county_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingest(
    county_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Trigger a scrape for a county. Admin only."""
    if user.role != "admin":
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError()

    result = await session.execute(select(County).where(County.id == county_id))
    county = result.scalar_one_or_none()
    if not county:
        raise NotFoundError("County")

    from app.core.sse import register_task_owner
    from app.workers.ingestion_tasks import scrape_county

    task = scrape_county.delay(str(county_id))
    register_task_owner(task.id, str(user.id))

    return {"task_id": task.id, "status": "queued", "county": county.name}


@router.get("/{county_id}/status")
async def ingest_status(
    county_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Get ingestion status for a county."""
    result = await session.execute(select(County).where(County.id == county_id))
    county = result.scalar_one_or_none()
    if not county:
        raise NotFoundError("County")

    return {
        "county": county.name,
        "is_active": county.is_active,
        "last_scraped_at": county.last_scraped_at.isoformat() if county.last_scraped_at else None,
        "last_lead_count": county.last_lead_count,
    }
