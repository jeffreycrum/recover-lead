from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BulkSkipTraceRequest(BaseModel):
    lead_ids: list[uuid.UUID]


class SkipTraceRequest(BaseModel):
    """Per-lookup overrides for POST /leads/{id}/skip-trace.

    Two lookup modes, chosen explicitly by the caller via ``name_only``:

    - **Address mode** (``name_only=False``, default): the effective
      mailing address (merged from overrides + lead stored data) must
      satisfy SkipSherpa's rule — street + (city AND state) OR zip.
      The backend rejects incomplete addresses with 400 instead of
      silently degrading to a name-only lookup, which for common names
      produces thousands of false positives and burns credits.
    - **Name-only mode** (``name_only=True``): the caller has opted in
      to a name-based lookup. Common when the lead has no property
      address at all (e.g. many FL counties). Address fields are
      ignored; provider sees only first/last name.

    String field overrides are used when the lead's scraped data is
    incomplete and the user has filled in missing parts via the dialog.
    Any field left None/empty falls back to the lead's stored value.
    """

    street: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=10)
    zip_code: str | None = Field(default=None, max_length=20)
    name_only: bool = False


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
