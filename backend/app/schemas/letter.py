from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class LetterGenerateRequest(BaseModel):
    lead_id: uuid.UUID
    letter_type: str = "tax_deed"  # tax_deed|foreclosure|excess_proceeds


class LetterBatchRequest(BaseModel):
    lead_ids: list[uuid.UUID]
    letter_type: str = "tax_deed"


class LetterUpdateRequest(BaseModel):
    content: str | None = None
    status: str | None = None  # draft|approved


class LetterResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    letter_type: str
    content: str
    status: str
    sent_at: datetime | None
    created_at: datetime
    # Inline lead fields
    case_number: str | None = None
    county_name: str | None = None
    owner_name: str | None = None
    surplus_amount: float | None = None


class LetterListResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    letter_type: str
    status: str
    created_at: datetime
    case_number: str | None = None
    county_name: str | None = None
    owner_name: str | None = None
