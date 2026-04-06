import json
import re
import uuid

import anthropic
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import LLMUsage
from app.rag.embeddings import build_lead_text, generate_lead_embedding
from app.rag.vector_search import find_similar_leads

logger = structlog.get_logger()

# Load Jinja2 templates
_template_env = Environment(
    loader=FileSystemLoader("app/rag/prompts"),
    autoescape=False,
)


async def qualify_lead(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
) -> dict:
    """Qualify a single lead using similar leads context + Claude.

    Returns {"quality_score": int, "reasoning": str}
    """
    # Build embedding for this lead
    lead_text = build_lead_text(
        case_number=lead_data["case_number"],
        owner_name=lead_data.get("owner_name"),
        property_address=lead_data.get("property_address"),
        property_city=lead_data.get("property_city"),
        surplus_amount=float(lead_data.get("surplus_amount", 0)),
        sale_type=lead_data.get("sale_type"),
        county_name=county_name,
    )
    embedding = generate_lead_embedding(lead_text)

    # Find similar leads for context
    similar = await find_similar_leads(
        session,
        embedding,
        county_id=lead_data.get("county_id"),
        limit=5,
        exclude_lead_id=lead_id,
    )

    # Render prompt
    template = _template_env.get_template("qualification.j2")
    prompt = template.render(
        case_number=lead_data["case_number"],
        county_name=county_name,
        state=lead_data.get("property_state", "FL"),
        owner_name=lead_data.get("owner_name"),
        property_address=lead_data.get("property_address"),
        surplus_amount=float(lead_data.get("surplus_amount", 0)),
        sale_type=lead_data.get("sale_type"),
        sale_date=lead_data.get("sale_date"),
        similar_leads=similar,
    )

    # Call Claude
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse response
    raw_text = response.content[0].text.strip()
    result = _parse_qualification_response(raw_text)

    # Log usage
    usage = LLMUsage(
        user_id=user_id,
        task_type="qualification",
        model="claude-sonnet-4-20250514",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        estimated_cost=(response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015) / 1000,
    )
    session.add(usage)

    return {
        "quality_score": result["quality_score"],
        "reasoning": result["reasoning"],
        "embedding": embedding,
    }


def _parse_qualification_response(text: str) -> dict:
    """Parse Claude's qualification response. Validates score is 1-10."""
    try:
        # Try direct JSON parse
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code blocks
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            logger.warning("qualification_parse_failed", raw=text[:200])
            return {"quality_score": 5, "reasoning": "Unable to parse qualification response"}

    score = data.get("quality_score", 5)
    if not isinstance(score, int) or score < 1 or score > 10:
        score = max(1, min(10, int(score)))

    reasoning = data.get("reasoning", "No reasoning provided")
    if len(reasoning) > 2000:
        reasoning = reasoning[:2000]

    return {"quality_score": score, "reasoning": reasoning}
