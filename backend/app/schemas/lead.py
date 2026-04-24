from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

# Qualification statuses that count as "exhausted" for the upsell nudge
QUALIFIED_STATUSES = {"qualified", "contacted", "signed", "filed", "paid", "closed"}


class LeadBrowseResponse(BaseModel):
    id: uuid.UUID
    county_name: str
    case_number: str
    parcel_id: str | None = None
    property_address: str | None
    property_city: str | None
    property_state: str | None
    surplus_amount: Decimal
    sale_date: date | None
    sale_type: str | None
    owner_name: str | None
    created_at: datetime


class SkipTracePersonResponse(BaseModel):
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    dob: str | None = None
    age: int | None = None
    deceased: bool = False
    property_owner: bool = False
    phones: list[dict] = []
    emails: list[dict] = []
    mailing_address: dict | None = None


class SkipTraceResultSummary(BaseModel):
    id: uuid.UUID
    status: str
    hit_count: int
    persons: list[SkipTracePersonResponse]
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
    skip_trace_results: list[SkipTraceResultSummary] = []


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
    parcel_id: str | None = None
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


class LeadActivityResponse(BaseModel):
    id: uuid.UUID
    activity_type: str
    description: str | None
    metadata_: dict | None = None
    created_at: datetime


class ActivityCreateRequest(BaseModel):
    description: str


VALID_CLOSED_REASONS = {"recovered", "declined", "unreachable", "expired", "other"}


class DealPayRequest(BaseModel):
    outcome_amount: Decimal
    fee_percentage: Decimal
    notes: str | None = None

    @field_validator("outcome_amount")
    @classmethod
    def outcome_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("outcome_amount must be positive")
        return v

    @field_validator("fee_percentage")
    @classmethod
    def fee_must_be_valid(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("fee_percentage must be between 0 and 100")
        return v


class DealCloseRequest(BaseModel):
    closed_reason: str
    notes: str | None = None

    @field_validator("closed_reason")
    @classmethod
    def reason_must_be_valid(cls, v: str) -> str:
        if v not in VALID_CLOSED_REASONS:
            valid = ", ".join(sorted(VALID_CLOSED_REASONS))
            raise ValueError(f"closed_reason must be one of: {valid}")
        return v


class CountyExhaustionResponse(BaseModel):
    county_id: uuid.UUID
    county_name: str
    state: str
    total_leads: int
    qualified_leads: int
    exhaustion_pct: float
