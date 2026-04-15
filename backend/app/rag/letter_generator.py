import asyncio
import uuid
from functools import partial
from pathlib import Path

import anthropic
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import LLMUsage

logger = structlog.get_logger()

_TEMPLATES_DIR = Path("app/templates")
_PROMPTS_DIR = Path("app/rag/prompts")

_prompt_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=False,
)

def _money(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


_state_template_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=False,
)
_state_template_env.filters["money"] = _money

_STATE_TEMPLATE_MAP: dict[str, str] = {
    "TX": "texas_excess_proceeds.j2",
    "OH": "ohio_excess_proceeds.j2",
    "CA": "california_excess_proceeds.j2",
    "GA": "georgia_excess_proceeds.j2",
}

# Rate limit: max 10 concurrent Claude calls
_semaphore = asyncio.Semaphore(10)


async def _get_sender_fields(session: AsyncSession, user_id: uuid.UUID) -> dict[str, str | None]:
    """Fetch user profile fields used as sender info in state templates."""
    from app.models.user import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {
            "sender_name": None,
            "sender_company": None,
            "sender_phone": None,
            "sender_email": None,
        }

    return {
        "sender_name": user.full_name or None,
        "sender_company": user.company_name,
        "sender_phone": user.phone,
        "sender_email": user.email,
    }


async def generate_letter_content(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
    state: str = "FL",
    letter_type: str = "tax_deed",
) -> str:
    """Generate a personalized outreach letter.

    For states with a Jinja2 template (TX, OH, CA, GA), renders the template
    directly without an LLM call. Falls back to Claude for all other states.
    """
    template_name = _STATE_TEMPLATE_MAP.get(state)

    if template_name:
        return await _render_state_template(session, user_id, lead_data, county_name, template_name)

    return await _generate_via_claude(session, user_id, lead_data, county_name, state, letter_type)


async def _render_state_template(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
    template_name: str,
) -> str:
    """Render a state-specific Jinja2 template directly (no LLM call)."""
    sender_fields = await _get_sender_fields(session, user_id)

    template = _state_template_env.get_template(template_name)
    content = template.render(
        owner_name=lead_data.get("owner_name"),
        recipient_name=lead_data.get("owner_name"),
        owner_address=lead_data.get("owner_last_known_address"),
        owner_last_known_address=lead_data.get("owner_last_known_address"),
        case_number=lead_data.get("case_number"),
        parcel_id=lead_data.get("parcel_id"),
        sale_date=lead_data.get("sale_date"),
        county_name=county_name,
        property_address=lead_data.get("property_address"),
        surplus_amount=lead_data.get("surplus_amount") or 0,
        **sender_fields,
    )

    logger.info(
        "state_template_rendered",
        user_id=str(user_id),
        template=template_name,
        county=county_name,
    )

    return content.strip()


async def _generate_via_claude(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
    state: str,
    letter_type: str,
) -> str:
    """Generate a letter via Claude (used for FL and states without a template)."""
    template = _prompt_env.get_template("letter.j2")
    prompt = template.render(
        owner_name=lead_data.get("owner_name"),
        owner_address=lead_data.get("owner_last_known_address"),
        case_number=lead_data["case_number"],
        county_name=county_name,
        state=state,
        property_address=lead_data.get("property_address"),
        property_city=lead_data.get("property_city"),
        property_state=lead_data.get("property_state"),
        property_zip=lead_data.get("property_zip"),
        surplus_amount=float(lead_data.get("surplus_amount") or 0),
        sale_type=letter_type.replace("_", " "),
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async with _semaphore:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                client.messages.create,
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            ),
        )

    content = response.content[0].text.strip()

    usage = LLMUsage(
        user_id=user_id,
        task_type="letter",
        model="claude-sonnet-4-20250514",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        estimated_cost=(response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015)
        / 1000,
    )
    session.add(usage)

    return content


async def generate_letters_batch(
    session: AsyncSession,
    user_id: uuid.UUID,
    leads_data: list[dict],
    county_names: dict[str, str],
    letter_type: str = "tax_deed",
) -> list[dict]:
    """Generate letters for multiple leads concurrently.

    Uses asyncio.gather with a semaphore to limit concurrency to 10.
    """
    tasks = [
        generate_letter_content(
            session=session,
            user_id=user_id,
            lead_data=lead,
            county_name=county_names.get(str(lead.get("county_id")), "Unknown"),
            state=lead.get("county_state") or lead.get("property_state") or "FL",
            letter_type=letter_type,
        )
        for lead in leads_data
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    generated = []
    for i, result in enumerate(results):
        lead = leads_data[i]
        if isinstance(result, Exception):
            logger.error(
                "letter_generation_failed",
                lead_id=str(lead.get("id")),
                error=str(result),
            )
            generated.append(
                {
                    "lead_id": str(lead.get("id")),
                    "status": "error",
                    "error": str(result),
                }
            )
        else:
            generated.append(
                {
                    "lead_id": str(lead.get("id")),
                    "status": "success",
                    "content": result,
                }
            )

    return generated
