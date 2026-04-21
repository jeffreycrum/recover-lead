import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import anthropic
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import LLMUsage

logger = structlog.get_logger()

_CONTRACTS_DIR = Path("app/contract_templates")
_PROMPTS_DIR = Path("app/rag/prompts")

_prompt_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)
_contract_env = Environment(loader=FileSystemLoader(str(_CONTRACTS_DIR)), autoescape=False)


def _money(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


_prompt_env.filters["money"] = _money
_contract_env.filters["money"] = _money

_semaphore = asyncio.Semaphore(4)

_CONTRACT_TEMPLATE_MAP: dict[str, str] = {
    "FL": "fl_recovery_agreement.j2",
    "CA": "ca_recovery_agreement.j2",
    "GA": "ga_recovery_agreement.j2",
    "TX": "tx_recovery_agreement.j2",
    "OH": "oh_recovery_agreement.j2",
}

# State-specific context passed into the clause-generation prompt. Keeps the
# prompt uniform across states while letting Claude cite the correct statute
# and sale nomenclature per jurisdiction.
_STATE_CONTEXT: dict[str, dict[str, str]] = {
    "FL": {
        "state_name": "Florida",
        "sale_proceeding": "tax deed sale or foreclosure proceeding",
        "surplus_statute": "Fla. Stat. § 197.582",
        "typical_timeline": "60 to 120 days",
    },
    "CA": {
        "state_name": "California",
        "sale_proceeding": "tax-defaulted property sale",
        "surplus_statute": "Cal. Rev. & Tax. Code § 4675",
        "typical_timeline": "90 to 180 days",
    },
    "GA": {
        "state_name": "Georgia",
        "sale_proceeding": "tax sale",
        "surplus_statute": "O.C.G.A. § 48-4-5",
        "typical_timeline": "90 to 180 days",
    },
    "TX": {
        "state_name": "Texas",
        "sale_proceeding": "tax sale",
        "surplus_statute": "Tex. Tax Code § 34.03",
        "typical_timeline": "90 to 180 days",
    },
    "OH": {
        "state_name": "Ohio",
        "sale_proceeding": "sheriff's or tax foreclosure sale",
        "surplus_statute": "Ohio Rev. Code § 2329.44",
        "typical_timeline": "90 to 180 days",
    },
}

_DEFAULT_STATE = "FL"


async def generate_contract_content(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
    state: str = "FL",
    contract_type: str = "recovery_agreement",
    fee_percentage: float = 0.0,
    agent_name: str = "",
) -> str:
    """Generate a filled contract via Claude narrative clause injection.

    Loads the state Jinja2 skeleton template, calls Claude to fill narrative
    clauses, merges them, and returns the final contract text.
    """
    state_key = state if state in _CONTRACT_TEMPLATE_MAP else _DEFAULT_STATE
    template_name = _CONTRACT_TEMPLATE_MAP[state_key]
    state_context = _STATE_CONTEXT[state_key]
    today = datetime.now(UTC).strftime("%B %d, %Y")

    clauses = await _generate_clauses_via_claude(
        session=session,
        user_id=user_id,
        lead_data=lead_data,
        county_name=county_name,
        fee_percentage=fee_percentage,
        agent_name=agent_name,
        state_context=state_context,
    )

    template = _contract_env.get_template(template_name)
    content = template.render(
        case_number=lead_data.get("case_number"),
        owner_name=lead_data.get("owner_name"),
        property_address=lead_data.get("property_address"),
        surplus_amount=lead_data.get("surplus_amount") or 0,
        county_name=county_name,
        agent_name=agent_name,
        fee_percentage=fee_percentage,
        effective_date=today,
        **clauses,
    )

    return content.strip()


async def _generate_clauses_via_claude(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict,
    county_name: str,
    fee_percentage: float,
    agent_name: str,
    state_context: dict[str, str],
) -> dict[str, str]:
    """Call Claude to generate narrative clauses. Returns a dict of clause_name -> text."""
    if not settings.anthropic_api_key:
        return _placeholder_clauses(fee_percentage, state_context)

    prompt_template = _prompt_env.get_template("contract.j2")
    prompt = prompt_template.render(
        case_number=lead_data.get("case_number"),
        county_name=county_name,
        property_address=lead_data.get("property_address"),
        surplus_amount=float(lead_data.get("surplus_amount") or 0),
        agent_name=agent_name,
        fee_percentage=fee_percentage,
        owner_name=lead_data.get("owner_name"),
        **state_context,
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async with _semaphore:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                client.messages.create,
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            ),
        )

    raw_text = response.content[0].text.strip()

    expected_clause_keys = frozenset(
        {
            "authorization_clause",
            "fee_clause",
            "timeline_clause",
            "warranty_clause",
            "governing_law_clause",
        }
    )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        parsed = json.loads(match.group()) if match else {}

    # Whitelist: only pass known clause keys to the template; fall back to
    # placeholders for any key that Claude omitted or added unexpectedly.
    placeholders = _placeholder_clauses(fee_percentage, state_context)
    clauses = {
        key: str(parsed[key]) if key in parsed else placeholders[key]
        for key in expected_clause_keys
    }

    usage = LLMUsage(
        user_id=user_id,
        task_type="contract",
        model="claude-sonnet-4-20250514",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        estimated_cost=(
            response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015
        )
        / 1000,
    )
    session.add(usage)

    logger.info(
        "contract_clauses_generated",
        user_id=str(user_id),
        county=county_name,
        input_tokens=response.usage.input_tokens,
    )

    return clauses


def _placeholder_clauses(
    fee_percentage: float, state_context: dict[str, str]
) -> dict[str, str]:
    """Fallback clauses used when the Anthropic API key is not configured.

    State-specific phrasing (governing law, typical timeline, statute citation)
    is injected from state_context so the fallback still matches the jurisdiction.
    """
    state_name = state_context["state_name"]
    typical_timeline = state_context["typical_timeline"]
    surplus_statute = state_context["surplus_statute"]
    return {
        "authorization_clause": (
            "AUTHORIZATION TO REPRESENT\n\n"
            "Client hereby authorizes Recovery Agent to act on Client's behalf in "
            "connection with the recovery of the Surplus Funds, including filing claims, "
            "communicating with courts and government agencies, and receiving disbursements. "
            "Client remains the beneficial owner of the Surplus Funds at all times."
        ),
        "fee_clause": (
            "CONTINGENCY FEE AGREEMENT\n\n"
            f"In consideration for Recovery Agent's services, Client agrees to pay Recovery Agent "
            f"a contingency fee of {fee_percentage}% of the gross Surplus Funds actually recovered."
            " No fee is owed if no recovery is made."
        ),
        "timeline_clause": (
            "TIMELINE AND BEST EFFORTS\n\n"
            "Recovery Agent shall use commercially reasonable efforts to recover"
            f" the Surplus Funds. {state_name} surplus claims typically resolve within"
            f" {typical_timeline} of filing."
            " Recovery Agent shall provide Client with periodic status updates."
        ),
        "warranty_clause": (
            "CLIENT WARRANTIES\n\n"
            "Client warrants that (i) Client is entitled to claim the Surplus Funds, "
            "(ii) Client has not assigned or encumbered any interest in the Surplus Funds, "
            "and (iii) Client will cooperate fully and provide all requested documentation."
        ),
        "governing_law_clause": (
            "GOVERNING LAW AND DISPUTE RESOLUTION\n\n"
            f"This Agreement is governed by the laws of the State of {state_name}, "
            f"and the disbursement of Surplus Funds is subject to {surplus_statute}. "
            "Any dispute shall first be submitted to non-binding mediation before litigation. "
            "Venue for any legal proceeding shall be the county identified in the Recitals."
        ),
    }
