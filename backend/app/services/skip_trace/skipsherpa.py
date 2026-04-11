"""Skip Sherpa skip trace provider implementation.

Skip Sherpa is a waterfall enrichment API. Critical features for RecoverLead:
- Name-only lookups (no address required)
- Deceased flags
- LLC/business owner piercing (separate endpoint)

API:
  PUT https://skipsherpa.com/api/beta6/person
    Body: {"person_lookups": [{"first_name", "middle_name", "last_name",
                                "mailing_addresses": [{"street","city","state","zipcode"}]}]}
    Response envelope: {"person_results": [{"persons": [{phone_numbers, emails, addresses}]}]}

  PUT https://skipsherpa.com/api/beta6/business
    Body: {"business_lookups": [{"business_name", "mailing_address":{...},
                                  "omit_registered_agents": false}]}
    Response envelope: {"business_results": [{"businesses": [{phone_numbers, emails, addresses}]}]}

  Auth: API-Key header
  404 = no match (not an error)
  Error envelope: {"status_code": 403, "issues": [{"detail": "..."}], "results": []}

Routing:
- Owner name looks like LLC/Corp/Trust -> /business
- Person name                          -> /person
"""

from __future__ import annotations

import re

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


# Business entity markers — match flipfinder's production list
BUSINESS_MARKERS = [
    " LLC",
    ",LLC",
    " INC",
    ",INC",
    " CORP",
    ",CORP",
    " CO.",
    " COMPANY",
    " TRUST",
    " L.P.",
    " LP",
    " L.L.C",
    " LLLP",
    " LLP",
    " PARTNERS",
    " HOLDINGS",
    " INVESTMENTS",
    " PROPERTIES",
    " REAL ESTATE",
    " CAPITAL",
    " GROUP",
    " VENTURES",
    " FUND",
    " ASSOC",
    " ESTATE OF",
    " LIVING TRUST",
    " REVOCABLE",
]


def _looks_like_business(name: str) -> bool:
    """Return True if the owner name appears to be an LLC/business entity."""
    if not name:
        return False
    u = name.upper()
    return any(m in u for m in BUSINESS_MARKERS)


def _build_address_dict(request: SkipTraceLookupRequest) -> dict | None:
    """Build a Skip Sherpa address dict.

    Skip Sherpa requires `street` whenever a mailing address is provided
    and validates min length >= 3 on string fields. If we don't have a
    street, return None so the caller omits the address entirely and
    falls back to a name-only lookup.
    """
    if not request.address or len(request.address) < 3:
        return None

    addr: dict = {"street": request.address}
    if request.city and len(request.city) >= 3:
        addr["city"] = request.city
    if request.state and len(request.state) >= 2:
        addr["state"] = request.state
    if request.zip_code and len(request.zip_code) >= 5:
        addr["zipcode"] = request.zip_code
    return addr


def _split_person_name(name: str) -> tuple[str, str, str]:
    """Split 'CURTIS S KRUGER' -> ('CURTIS', 'S', 'KRUGER').

    Multi-party names joined with commas (e.g. 'JOHN SMITH,JANE SMITH')
    only use the first party.
    """
    primary = name.split(",")[0].strip()
    parts = primary.split()
    if not parts:
        return ("", "", "")
    if len(parts) == 1:
        return ("", "", parts[0])
    if len(parts) == 2:
        return (parts[0], "", parts[1])
    return (parts[0], " ".join(parts[1:-1]), parts[-1])


class SkipSherpaProvider:
    """Skip Sherpa waterfall enrichment provider."""

    def __init__(self, api_key: str, base_url: str = "https://skipsherpa.com/api/beta6"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, request: SkipTraceLookupRequest) -> SkipTraceLookupResponse:
        """Real-time lookup. Routes to /person or /business based on name."""
        if not self.api_key:
            logger.error("skipsherpa_no_api_key")
            raise RuntimeError("SKIPSHERPA_API_KEY is not configured")

        # Build combined owner name (Tracerfy-style request uses split fields;
        # we join them to apply business-name detection)
        name = " ".join(
            filter(None, [request.first_name, request.last_name])
        ).strip()

        if not name:
            logger.warning("skipsherpa_empty_name")
            return SkipTraceLookupResponse(hit=False, persons=[], raw={})

        async with httpx.AsyncClient(
            timeout=60.0,
            headers={
                "API-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        ) as client:
            if _looks_like_business(name):
                return await self._lookup_business(client, name, request)
            else:
                return await self._lookup_person(client, name, request)

    async def _lookup_person(
        self,
        client: httpx.AsyncClient,
        name: str,
        request: SkipTraceLookupRequest,
    ) -> SkipTraceLookupResponse:
        first, middle, last = _split_person_name(name)
        person_lookup: dict = {}
        # Skip Sherpa validates min length >= 3 on name fields
        if first and len(first) >= 3:
            person_lookup["first_name"] = first
        if middle and len(middle) >= 3:
            person_lookup["middle_name"] = middle
        if last and len(last) >= 3:
            person_lookup["last_name"] = last

        # Only send mailing_addresses if we actually have address data —
        # Skip Sherpa rejects empty/short field values with 400.
        addr = _build_address_dict(request)
        if addr:
            person_lookup["mailing_addresses"] = [addr]

        body = {"person_lookups": [person_lookup]}
        url = f"{self.base_url}/person"
        logger.info("skipsherpa_request", url=url, endpoint="person")

        data = await self._put_json(client, url, body)
        if data is None:  # 404 = no match
            return SkipTraceLookupResponse(hit=False, persons=[], raw={})

        # Response envelope: person_results[0].persons[]
        results = (
            data.get("person_results") or data.get("results") or []
        )
        persons_raw: list = []
        if results and isinstance(results[0], dict):
            persons_raw = results[0].get("persons") or []

        persons = [_parse_entity(p) for p in persons_raw if isinstance(p, dict)]
        hit = any((p.phones or p.emails or p.mailing_address) for p in persons)

        logger.info(
            "skipsherpa_lookup_complete",
            endpoint="person",
            hit=hit,
            person_count=len(persons),
        )
        return SkipTraceLookupResponse(hit=hit, persons=persons, raw=data)

    async def _lookup_business(
        self,
        client: httpx.AsyncClient,
        name: str,
        request: SkipTraceLookupRequest,
    ) -> SkipTraceLookupResponse:
        business_lookup: dict = {
            "business_name": name,
            "omit_registered_agents": False,
        }
        addr = _build_address_dict(request)
        if addr:
            business_lookup["mailing_address"] = addr

        body = {"business_lookups": [business_lookup]}
        url = f"{self.base_url}/business"
        logger.info("skipsherpa_request", url=url, endpoint="business")

        data = await self._put_json(client, url, body)
        if data is None:
            return SkipTraceLookupResponse(hit=False, persons=[], raw={})

        # Response envelope: business_results[0].businesses[]
        results = (
            data.get("business_results") or data.get("results") or []
        )
        businesses_raw: list = []
        if results and isinstance(results[0], dict):
            businesses_raw = results[0].get("businesses") or []

        persons = [_parse_entity(b) for b in businesses_raw if isinstance(b, dict)]
        hit = any((p.phones or p.emails or p.mailing_address) for p in persons)

        logger.info(
            "skipsherpa_lookup_complete",
            endpoint="business",
            hit=hit,
            person_count=len(persons),
        )
        return SkipTraceLookupResponse(hit=hit, persons=persons, raw=data)

    async def _put_json(
        self, client: httpx.AsyncClient, url: str, body: dict
    ) -> dict | None:
        """PUT a JSON body. Returns parsed response, or None for 404 (no match).

        Raises on real errors (bad key, server error, etc.) with the
        'issues[0].detail' message from Skip Sherpa's error envelope.
        """
        response = await client.put(url, json=body)
        status = response.status_code
        body_text = response.text

        logger.info(
            "skipsherpa_response",
            status_code=status,
            body_preview=body_text[:500],
        )

        # 404 = no match — not an error
        if status == 404:
            return None

        if status >= 400:
            # Try to extract the issue detail from Skip Sherpa's error envelope
            try:
                err_json = response.json()
                issues = err_json.get("issues") or []
                detail = (
                    (issues[0].get("detail") if issues else None)
                    or (issues[0].get("code_str") if issues else None)
                    or response.reason_phrase
                    or "error"
                )
            except Exception:
                detail = body_text[:200] or response.reason_phrase or "error"
            logger.error(
                "skipsherpa_http_error",
                status_code=status,
                detail=detail,
                body=body_text[:2000],
            )
            raise RuntimeError(f"Skip Sherpa {status}: {detail}")

        return response.json()


def _parse_entity(entity: dict) -> PersonResult:
    """Extract phones/emails/address from a Skip Sherpa person or business entity.

    Both schemas share phone_numbers, emails, and addresses arrays.
    """
    phones: list[PhoneResult] = []
    for p in entity.get("phone_numbers") or []:
        if not isinstance(p, dict):
            continue
        # Prefer local_format, fall back to e164
        number = p.get("local_format") or p.get("e164_format") or ""
        if number:
            phones.append(
                PhoneResult(
                    number=str(number),
                    type=str(p.get("type") or p.get("line_type") or ""),
                    dnc=bool(p.get("dnc") or p.get("do_not_call") or False),
                    carrier=str(p.get("carrier") or ""),
                    rank=int(p.get("rank") or 0),
                )
            )

    emails: list[EmailResult] = []
    for e in entity.get("emails") or []:
        if not isinstance(e, dict):
            continue
        addr = e.get("email_address") or ""
        if addr:
            emails.append(EmailResult(email=str(addr), rank=int(e.get("rank") or 0)))

    # Mailing address from addresses[0] — has delivery_line1 + last_line
    mailing_address = None
    addresses = entity.get("addresses") or []
    if addresses and isinstance(addresses[0], dict):
        first_addr = addresses[0]
        line1 = first_addr.get("delivery_line1") or first_addr.get("street") or ""
        last_line = first_addr.get("last_line") or ""
        city = first_addr.get("city") or ""
        state = first_addr.get("state") or ""
        zipcode = first_addr.get("zipcode") or first_addr.get("zip") or ""
        # Parse "city, state zip" from last_line if individual fields missing
        if last_line and not (city and state):
            m = re.match(r"([^,]+),\s*(\w{2})\s+(\d{5})", last_line)
            if m:
                city = city or m.group(1).strip()
                state = state or m.group(2)
                zipcode = zipcode or m.group(3)
        mailing_address = AddressResult(
            street=str(line1),
            city=str(city),
            state=str(state),
            zip_code=str(zipcode),
        )

    deceased = bool(
        entity.get("deceased")
        or entity.get("is_deceased")
        or entity.get("deceased_flag")
        or False
    )

    return PersonResult(
        first_name=str(entity.get("first_name") or ""),
        last_name=str(entity.get("last_name") or ""),
        full_name=str(
            entity.get("full_name")
            or entity.get("business_name")
            or entity.get("name")
            or ""
        ),
        dob=entity.get("dob") or entity.get("date_of_birth"),
        age=entity.get("age"),
        deceased=deceased,
        property_owner=bool(entity.get("property_owner") or False),
        litigator=bool(entity.get("litigator") or False),
        mailing_address=mailing_address,
        phones=phones,
        emails=emails,
    )
