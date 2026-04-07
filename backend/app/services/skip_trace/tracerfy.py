"""Tracerfy skip trace provider implementation."""

import httpx
import structlog

from app.services.skip_trace import (
    AddressResult,
    EmailResult,
    PersonResult,
    PhoneResult,
    SkipTraceLookupRequest,
    SkipTraceLookupResponse,
)

logger = structlog.get_logger()


class TracerfyProvider:
    """Tracerfy real-time skip trace via POST /trace/lookup/."""

    def __init__(self, api_key: str, base_url: str = "https://tracerfy.com/v1/api"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, request: SkipTraceLookupRequest) -> SkipTraceLookupResponse:
        """Real-time single lookup. Returns immediately. $0.10/hit, $0.00/miss."""
        payload = {
            "address": request.address,
            "city": request.city,
            "state": request.state,
        }
        if request.zip_code:
            payload["zip"] = request.zip_code
        if request.first_name:
            payload["first_name"] = request.first_name
        if request.last_name:
            payload["last_name"] = request.last_name
        if request.find_owner:
            payload["find_owner"] = True

        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = await client.post(
                f"{self.base_url}/trace/lookup/",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        persons = [self._parse_person(p) for p in data.get("results", [])]
        hit = len(persons) > 0

        logger.info(
            "tracerfy_lookup",
            hit=hit,
            person_count=len(persons),
            address=request.address,
        )

        return SkipTraceLookupResponse(hit=hit, persons=persons, raw=data)

    @staticmethod
    def _parse_person(raw: dict) -> PersonResult:
        phones = [
            PhoneResult(
                number=p.get("number", ""),
                type=p.get("type", ""),
                dnc=p.get("dnc", False),
                carrier=p.get("carrier", ""),
                rank=p.get("rank", 0),
            )
            for p in raw.get("phones", [])
        ]

        emails = [
            EmailResult(
                email=e.get("email", ""),
                rank=e.get("rank", 0),
            )
            for e in raw.get("emails", [])
        ]

        addr_raw = raw.get("mailing_address", {})
        mailing_address = None
        if addr_raw:
            mailing_address = AddressResult(
                street=addr_raw.get("street", ""),
                city=addr_raw.get("city", ""),
                state=addr_raw.get("state", ""),
                zip_code=addr_raw.get("zip", ""),
            )

        return PersonResult(
            first_name=raw.get("first_name", ""),
            last_name=raw.get("last_name", ""),
            full_name=raw.get("full_name", ""),
            dob=raw.get("dob"),
            age=raw.get("age"),
            deceased=raw.get("deceased", False),
            property_owner=raw.get("property_owner", False),
            litigator=raw.get("litigator", False),
            mailing_address=mailing_address,
            phones=phones,
            emails=emails,
        )
