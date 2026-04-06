import asyncio
import uuid
from functools import partial

import anthropic
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import LLMUsage

logger = structlog.get_logger()

_template_env = Environment(
    loader=FileSystemLoader("app/rag/prompts"),
    autoescape=False,
)

# Rate limit: max 10 concurrent Claude calls
_semaphore = asyncio.Semaphore(10)


async def generate_letter_content(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
    letter_type: str = "tax_deed",
) -> str:
    """Generate a personalized outreach letter using Claude."""
    template = _template_env.get_template("letter.j2")
    prompt = template.render(
        owner_name=lead_data.get("owner_name"),
        owner_address=lead_data.get("owner_last_known_address"),
        case_number=lead_data["case_number"],
        county_name=county_name,
        state=lead_data.get("property_state", "FL"),
        property_address=lead_data.get("property_address"),
        property_city=lead_data.get("property_city"),
        property_state=lead_data.get("property_state"),
        property_zip=lead_data.get("property_zip"),
        surplus_amount=float(lead_data.get("surplus_amount", 0)),
        sale_type=letter_type.replace("_", " "),
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async with _semaphore:
        # Run sync Anthropic call in thread to avoid blocking
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

    # Log usage
    usage = LLMUsage(
        user_id=user_id,
        task_type="letter",
        model="claude-sonnet-4-20250514",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        estimated_cost=(response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015) / 1000,
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
            generated.append({
                "lead_id": str(lead.get("id")),
                "status": "error",
                "error": str(result),
            })
        else:
            generated.append({
                "lead_id": str(lead.get("id")),
                "status": "success",
                "content": result,
            })

    return generated
