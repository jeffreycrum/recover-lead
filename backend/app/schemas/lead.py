from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class LeadBrowseResponse(BaseModel):
    id: uuid.UUID
    county_name: str
    case_number: str
    property_address: str | None
    property_city: str | None
    property_state: str | None
    surplus_amount: Decimal
    sale_date: date | None
    sale_type: str | None
    owner_name: str | None
    created_at: datetime


class LeadDetailResponse(BaseModel):
    id: uuid.UUID
    county_id: uuid.UUID
    county_name: str
    case_number: str
    parcel_id: str | None
    property_address: str | None
    property_city: str | None
    property_state: str | None
    property_zip: str | None
    surplus_amount: Decimal
    sale_date: date | None
    sale_type: str | None
    owner_name: str | None
    owner_last_known_address: str | None
    contacts: list[LeadContactResponse]
    user_lead: UserLeadResponse | None


class LeadContactResponse(BaseModel):
    id: uuid.UUID
    contact_type: str
    contact_value: str
    source: str | None
    confidence: float
    is_verified: bool


class UserLeadResponse(BaseModel):
    id: uuid.UUID
    status: str
    quality_score: int | None
    quality_reasoning: str | None
    priority: str | None
    created_at: datetime
    updated_at: datetime


class MyLeadResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    status: str
    quality_score: int | None
    priority: str | None
    created_at: datetime
    # Inline lead fields
    county_name: str
    case_number: str
    property_address: str | None
    property_city: str | None
    surplus_amount: Decimal
    sale_date: date | None
    owner_name: str | None


class LeadUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None


class CursorPage(BaseModel):
    items: list
    next_cursor: str | None
    has_more: bool


class BulkQualifyRequest(BaseModel):
    lead_ids: list[uuid.UUID]


class ClaimResponse(BaseModel):
    user_lead_id: uuid.UUID
    lead_id: uuid.UUID
    status: str
