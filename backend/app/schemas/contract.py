from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

VALID_CONTRACT_TYPES = {"recovery_agreement"}
VALID_CONTRACT_STATUSES = {"draft", "approved", "signed"}
VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved"},
    "approved": {"signed"},
    "signed": set(),
}


class ContractGenerateRequest(BaseModel):
    lead_id: uuid.UUID
    contract_type: str = "recovery_agreement"
    fee_percentage: Decimal
    agent_name: str

    @field_validator("contract_type")
    @classmethod
    def contract_type_must_be_valid(cls, v: str) -> str:
        if v not in VALID_CONTRACT_TYPES:
            valid = ", ".join(sorted(VALID_CONTRACT_TYPES))
            raise ValueError(f"contract_type must be one of: {valid}")
        return v

    @field_validator("fee_percentage")
    @classmethod
    def fee_must_be_valid(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("fee_percentage must be between 0 and 100")
        return v

    @field_validator("agent_name")
    @classmethod
    def agent_name_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("agent_name must not be empty")
        return v[:255]


class ContractUpdateRequest(BaseModel):
    content: str | None = Field(default=None, max_length=500_000)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CONTRACT_STATUSES:
            valid = ", ".join(sorted(VALID_CONTRACT_STATUSES))
            raise ValueError(f"status must be one of: {valid}")
        return v


class ContractListResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    contract_type: str
    status: str
    fee_percentage: Decimal | None
    agent_name: str | None
    created_at: datetime
    # Inline lead fields for list display
    case_number: str
    county_name: str
    owner_name: str | None
    surplus_amount: Decimal


class ContractResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    user_id: uuid.UUID
    contract_type: str
    content: str
    status: str
    fee_percentage: Decimal | None
    agent_name: str | None
    created_at: datetime
    updated_at: datetime
    # Inline lead fields
    case_number: str
    county_name: str
    owner_name: str | None
    surplus_amount: Decimal
    property_address: str | None
