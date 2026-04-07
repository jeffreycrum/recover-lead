from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BulkSkipTraceRequest(BaseModel):
    lead_ids: list[uuid.UUID]


class PhoneResponse(BaseModel):
    number: str
    type: str = ""
    dnc: bool = False
    carrier: str = ""
    rank: int = 0


class EmailResponse(BaseModel):
    email: str
    rank: int = 0


class AddressResponse(BaseModel):
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""


class PersonResponse(BaseModel):
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    dob: str | None = None
    age: int | None = None
    deceased: bool = False
    property_owner: bool = False
    litigator: bool = False
    mailing_address: AddressResponse | None = None
    phones: list[PhoneResponse] = []
    emails: list[EmailResponse] = []


class SkipTraceResultResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    provider: str
    status: str
    persons: list[PersonResponse] = []
    hit_count: int = 0
    cost: float = 0.0
    created_at: datetime
