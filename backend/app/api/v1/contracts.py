import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientCreditsError, NotFoundError
from app.db.session import get_async_session
from app.dependencies import get_current_user
from app.models.contract import Contract
from app.models.county import County
from app.models.lead import Lead, UserLead
from app.models.user import User
from app.schemas.contract import (
    VALID_STATUS_TRANSITIONS,
    ContractGenerateRequest,
    ContractListResponse,
    ContractResponse,
    ContractUpdateRequest,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/contracts", tags=["contracts"])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_contract(
    req: ContractGenerateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Generate a contract for a claimed lead. Returns task_id for polling."""
    # Verify lead is claimed by this user
    ul_result = await session.execute(
        select(UserLead).where(
            UserLead.user_id == user.id,
            UserLead.lead_id == req.lead_id,
        )
    )
    if not ul_result.scalar_one_or_none():
        raise NotFoundError("Claimed lead")

    from app.services.billing_service import reserve_usage

    reservation = await reserve_usage(session, user.id, "letter", count=1)
    if not reservation.allowed:
        raise InsufficientCreditsError()

    from app.core.sse import register_task_owner
    from app.workers.contract_tasks import generate_contract_task

    task = generate_contract_task.delay(
        str(user.id),
        str(req.lead_id),
        req.contract_type,
        float(req.fee_percentage),
        req.agent_name,
        bool(reservation.overage_count),
        reservation.period_start_iso,
    )
    register_task_owner(task.id, str(user.id))

    return {"task_id": task.id, "status": "queued", "message": "Contract generation queued"}


@router.get("", response_model=list[ContractListResponse])
async def list_contracts(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE),
) -> list[ContractListResponse]:
    """List contracts for the current user with cursor pagination."""
    query = (
        select(
            Contract,
            Lead.case_number.label("case_number"),
            Lead.owner_name.label("owner_name"),
            Lead.surplus_amount.label("surplus_amount"),
            Lead.property_address.label("property_address"),
            County.name.label("county_name"),
        )
        .join(Lead, Contract.lead_id == Lead.id)
        .join(County, Lead.county_id == County.id)
        .where(Contract.user_id == user.id)
        .order_by(Contract.created_at.desc(), Contract.id)
    )

    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
            cursor_result = await session.execute(
                select(Contract.created_at).where(
                    Contract.id == cursor_uuid, Contract.user_id == user.id
                )
            )
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time is not None:
                query = query.where(
                    (Contract.created_at < cursor_time)
                    | ((Contract.created_at == cursor_time) & (Contract.id > cursor_uuid))
                )
        except ValueError:
            pass

    query = query.limit(limit + 1)
    result = await session.execute(query)
    rows = result.all()

    items = rows[:limit]
    return [
        ContractListResponse(
            id=contract.id,
            lead_id=contract.lead_id,
            contract_type=contract.contract_type,
            status=contract.status,
            fee_percentage=contract.fee_percentage,
            agent_name=contract.agent_name,
            created_at=contract.created_at,
            case_number=case_number,
            county_name=county_name,
            owner_name=owner_name,
            surplus_amount=surplus_amount,
        )
        for (
            contract,
            case_number,
            owner_name,
            surplus_amount,
            property_address,
            county_name,
        ) in items
    ]


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    """Get contract detail."""
    result = await session.execute(
        select(
            Contract,
            Lead.case_number.label("case_number"),
            Lead.owner_name.label("owner_name"),
            Lead.surplus_amount.label("surplus_amount"),
            Lead.property_address.label("property_address"),
            County.name.label("county_name"),
        )
        .join(Lead, Contract.lead_id == Lead.id)
        .join(County, Lead.county_id == County.id)
        .where(Contract.id == contract_id, Contract.user_id == user.id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Contract")

    contract, case_number, owner_name, surplus_amount, property_address, county_name = row
    return ContractResponse(
        id=contract.id,
        lead_id=contract.lead_id,
        user_id=contract.user_id,
        contract_type=contract.contract_type,
        content=contract.content,
        status=contract.status,
        fee_percentage=contract.fee_percentage,
        agent_name=contract.agent_name,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
        case_number=case_number,
        county_name=county_name,
        owner_name=owner_name,
        surplus_amount=surplus_amount,
        property_address=property_address,
    )


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: uuid.UUID,
    req: ContractUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> ContractResponse:
    """Edit content (draft only) or advance status (draft→approved→signed)."""
    result = await session.execute(
        select(
            Contract,
            Lead.case_number.label("case_number"),
            Lead.owner_name.label("owner_name"),
            Lead.surplus_amount.label("surplus_amount"),
            Lead.property_address.label("property_address"),
            County.name.label("county_name"),
        )
        .join(Lead, Contract.lead_id == Lead.id)
        .join(County, Lead.county_id == County.id)
        .where(Contract.id == contract_id, Contract.user_id == user.id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Contract")

    contract, case_number, owner_name, surplus_amount, property_address, county_name = row

    if req.content is not None:
        if contract.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "NOT_EDITABLE",
                    "message": "Content can only be edited while the contract is in draft status",
                },
            )
        contract.content = req.content

    if req.status is not None:
        allowed_next = VALID_STATUS_TRANSITIONS.get(contract.status, set())
        if req.status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_TRANSITION",
                    "message": (
                        f"Cannot transition from '{contract.status}' to '{req.status}'. "
                        f"Allowed: {sorted(allowed_next) or 'none'}"
                    ),
                },
            )
        contract.status = req.status

    await session.flush()

    return ContractResponse(
        id=contract.id,
        lead_id=contract.lead_id,
        user_id=contract.user_id,
        contract_type=contract.contract_type,
        content=contract.content,
        status=contract.status,
        fee_percentage=contract.fee_percentage,
        agent_name=contract.agent_name,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
        case_number=case_number,
        county_name=county_name,
        owner_name=owner_name,
        surplus_amount=surplus_amount,
        property_address=property_address,
    )


@router.get("/{contract_id}/pdf")
async def download_contract_pdf(
    contract_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Download contract as a print-ready PDF."""
    result = await session.execute(
        select(Contract, Lead.case_number.label("case_number"))
        .join(Lead, Contract.lead_id == Lead.id)
        .where(Contract.id == contract_id, Contract.user_id == user.id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Contract")

    contract, case_number = row

    from app.services.letter_service import generate_pdf

    pdf_bytes = generate_pdf(
        content=contract.content,
        case_number=case_number,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="contract-{contract_id}.pdf"'
            )
        },
    )
