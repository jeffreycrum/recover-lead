"""Skip Sherpa skip trace provider implementation.

Skip Sherpa is a waterfall enrichment API that accepts partial input
(name only, address only, or any combination) and cross-references
multiple data sources to fill in gaps. Critical features for RecoverLead:

- Name-only lookups (Tracerfy requires address, Skip Sherpa does not)
- Deceased flags
- Relative/heir graph
- LLC -> individual owner piercing
- Property + mortgage + equity data

API docs: https://skipsherpa.com/api/docs/elements (Stoplight-hosted)
Pricing:  $0.08-0.15 per hit, $30/mo = 200 hits @ $0.15

NOTE: Request/response field names below are based on Skip Sherpa's
marketing pages since their docs are JS-rendered and not scrapable.
Verify field names against the actual API response once we have a
real API key. The verbose logging on every call will show mismatches.
"""

from __future__ import annotations

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


class SkipSherpaProvider:
    """Skip Sherpa waterfall enrichment provider."""

    def __init__(self, api_key: str, base_url: str = "https://api.skipsherpa.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, request: SkipTraceLookupRequest) -> SkipTraceLookupResponse:
        """Real-time lookup. Accepts partial data — name alone is fine."""
        if not self.api_key:
            logger.error("skipsherpa_no_api_key")
            raise RuntimeError("SKIPSHERPA_API_KEY is not configured")

        # Only include fields we have — waterfall fills in the rest
        payload: dict = {}
        if request.first_name:
            payload["first_name"] = request.first_name
        if request.last_name:
            payload["last_name"] = request.last_name
        if request.address:
            payload["address"] = request.address
        if request.city:
            payload["city"] = request.city
        if request.state:
            payload["state"] = request.state
        if request.zip_code:
            payload["zip"] = request.zip_code

        if not payload:
            logger.warning("skipsherpa_empty_request")
            return SkipTraceLookupResponse(hit=False, persons=[], raw={})

        url = f"{self.base_url}/skip-trace"
        logger.info(
            "skipsherpa_request",
            url=url,
            payload_keys=list(payload.keys()),
        )

        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        ) as client:
            response = await client.post(url, json=payload)
            logger.info(
                "skipsherpa_response",
                status_code=response.status_code,
                body_preview=response.text[:500],
            )
            if response.status_code >= 400:
                logger.error(
                    "skipsherpa_http_error",
                    status_code=response.status_code,
                    body=response.text[:2000],
                )
            response.raise_for_status()
            data = response.json()

        persons_raw = data.get("results") or data.get("persons") or []
        if isinstance(persons_raw, dict):
            persons_raw = [persons_raw]

        persons = [self._parse_person(p) for p in persons_raw if p]
        hit = any(
            (p.phones or p.emails or p.mailing_address) for p in persons
        )

        logger.info(
            "skipsherpa_lookup_complete",
            hit=hit,
            person_count=len(persons),
            has_input_address=bool(request.address),
        )

        return SkipTraceLookupResponse(hit=hit, persons=persons, raw=data)

    @staticmethod
    def _parse_person(raw: dict) -> PersonResult:
        """Map Skip Sherpa person object to our PersonResult.

        Field names are best-effort guesses based on marketing pages.
        Verify against actual responses and adjust as needed.
        """
        # Phones — try multiple common field names
        phones_raw = (
            raw.get("phones")
            or raw.get("phone_numbers")
            or raw.get("phoneNumbers")
            or []
        )
        phones = [
            PhoneResult(
                number=str(p.get("number") or p.get("phone") or ""),
                type=str(p.get("type") or p.get("phone_type") or ""),
                dnc=bool(p.get("dnc") or p.get("do_not_call") or False),
                carrier=str(p.get("carrier") or ""),
                rank=int(p.get("rank") or p.get("confidence") or 0),
            )
            for p in phones_raw
            if isinstance(p, dict)
        ]

        emails_raw = (
            raw.get("emails")
            or raw.get("email_addresses")
            or raw.get("emailAddresses")
            or []
        )
        emails = [
            EmailResult(
                email=str(e.get("email") or e.get("address") or ""),
                rank=int(e.get("rank") or e.get("confidence") or 0),
            )
            for e in emails_raw
            if isinstance(e, dict)
        ]

        # Mailing address — try common shapes
        addr_raw = (
            raw.get("mailing_address")
            or raw.get("address")
            or raw.get("current_address")
            or {}
        )
        mailing_address = None
        if isinstance(addr_raw, dict) and addr_raw:
            mailing_address = AddressResult(
                street=str(addr_raw.get("street") or addr_raw.get("line1") or ""),
                city=str(addr_raw.get("city") or ""),
                state=str(addr_raw.get("state") or ""),
                zip_code=str(addr_raw.get("zip") or addr_raw.get("zip_code") or ""),
            )

        # Deceased flag — critical for surplus funds
        deceased = bool(
            raw.get("deceased")
            or raw.get("is_deceased")
            or raw.get("deceased_flag")
            or False
        )

        return PersonResult(
            first_name=str(raw.get("first_name") or raw.get("firstName") or ""),
            last_name=str(raw.get("last_name") or raw.get("lastName") or ""),
            full_name=str(
                raw.get("full_name")
                or raw.get("fullName")
                or raw.get("name")
                or ""
            ),
            dob=raw.get("dob") or raw.get("date_of_birth"),
            age=raw.get("age"),
            deceased=deceased,
            property_owner=bool(raw.get("property_owner") or False),
            litigator=bool(raw.get("litigator") or False),
            mailing_address=mailing_address,
            phones=phones,
            emails=emails,
        )
