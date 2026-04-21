import asyncio
import json
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import anthropic
import structlog
from jinja2 import Environment, FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import LLMUsage
from app.rag.state_registry import CONTRACT_TEMPLATE_MAP as _CONTRACT_TEMPLATE_MAP
from app.rag.state_registry import DEFAULT_STATE as _DEFAULT_STATE
from app.rag.state_registry import STATE_CONTEXT as _STATE_CONTEXT
from app.rag.state_registry import ContractStateContext, get_state_registry_entry

logger = structlog.get_logger()

_MODULE_DIR = Path(__file__).resolve().parent
_CONTRACTS_DIR = _MODULE_DIR.parent / "contract_templates"
_PROMPTS_DIR = _MODULE_DIR / "prompts"

_prompt_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)
_contract_env = SandboxedEnvironment(
    loader=FileSystemLoader(str(_CONTRACTS_DIR)),
    autoescape=False,
)

_EXPECTED_CLAUSE_KEYS = (
    "authorization_clause",
    "fee_clause",
    "timeline_clause",
    "warranty_clause",
    "governing_law_clause",
)
_CLAUSE_HEADINGS = {
    "authorization_clause": "AUTHORIZATION TO REPRESENT",
    "fee_clause": "CONTINGENCY FEE AGREEMENT",
    "timeline_clause": "TIMELINE AND BEST EFFORTS",
    "warranty_clause": "CLIENT WARRANTIES",
    "governing_law_clause": "GOVERNING LAW AND DISPUTE RESOLUTION",
}
_TEMPLATE_MARKERS = ("{{", "{%", "{#")
_RAW_TEXT_LOG_LIMIT = 500


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


_prompt_env.filters["money"] = _money
_contract_env.filters["money"] = _money

# Contracts spend more prompt + render time than letters, so keep a tighter
# concurrency cap for legal document generation.
_semaphore = asyncio.Semaphore(4)


async def generate_contract_content(
    session: AsyncSession,
    user_id: uuid.UUID,
    lead_data: dict[str, Any],
    county_name: str,
    state: str = _DEFAULT_STATE,
    contract_type: str = "recovery_agreement",
    fee_percentage: float = 0.0,
    agent_name: str = "",
) -> str:
    """Generate a filled contract via Claude narrative clause injection."""
    del contract_type  # Reserved for future state/template branching.

    state_key = _normalize_contract_state(state)
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
    lead_data: dict[str, Any],
    county_name: str,
    fee_percentage: float,
    agent_name: str,
    state_context: ContractStateContext,
) -> dict[str, str]:
    """Call Claude to generate narrative clauses."""
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
        **state_context.to_prompt_context(),
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
    parsed = _parse_claude_clause_payload(raw_text)
    clauses = _coerce_clauses(
        parsed=parsed,
        raw_text=raw_text,
        fee_percentage=fee_percentage,
        state_context=state_context,
    )

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
        state=state_context.state_name,
        input_tokens=response.usage.input_tokens,
    )

    return clauses


def _placeholder_clauses(
    fee_percentage: float,
    state_context: ContractStateContext,
) -> dict[str, str]:
    """Fallback clauses used when the Anthropic API key is not configured."""
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
            " the Surplus Funds."
            f" {state_context.state_name} surplus claims typically resolve within"
            f" {state_context.typical_timeline} of filing."
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
            f"This Agreement is governed by the laws of the State of {state_context.state_name}, "
            f"and the disbursement of Surplus Funds is subject to {state_context.surplus_statute}. "
            "Any dispute shall first be submitted to non-binding mediation before litigation. "
            "Venue for any legal proceeding shall be the county identified in the Recitals."
        ),
    }


def _normalize_contract_state(state: str | None) -> str:
    entry = get_state_registry_entry(state)
    if entry is None:
        raise ValueError(f"Unsupported contract state: {state!r}")
    return entry.code


def _parse_claude_clause_payload(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match is None:
            _log_clause_payload_warning("contract_clause_json_parse_failed", raw_text)
            raise ValueError("Claude returned malformed contract clause JSON") from exc

        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError as fallback_exc:
            _log_clause_payload_warning("contract_clause_json_parse_failed", raw_text)
            raise ValueError("Claude returned malformed contract clause JSON") from fallback_exc

    if not isinstance(parsed, dict):
        _log_clause_payload_warning(
            "contract_clause_json_shape_invalid",
            raw_text,
            payload_type=type(parsed).__name__,
        )
        raise ValueError("Claude returned a non-object contract clause payload")

    return parsed


def _coerce_clauses(
    parsed: Mapping[str, Any],
    raw_text: str,
    fee_percentage: float,
    state_context: ContractStateContext,
) -> dict[str, str]:
    placeholders = _placeholder_clauses(fee_percentage, state_context)
    degraded_keys: list[str] = []
    clauses: dict[str, str] = {}

    for key in _EXPECTED_CLAUSE_KEYS:
        validated_clause = _validate_clause_text(key, parsed.get(key))
        if validated_clause is None:
            degraded_keys.append(key)
            clauses[key] = placeholders[key]
            continue
        clauses[key] = validated_clause

    if degraded_keys:
        _log_clause_payload_warning(
            "contract_clause_payload_degraded",
            raw_text,
            degraded_keys=degraded_keys,
            state=state_context.state_name,
        )

    return clauses


def _validate_clause_text(key: str, value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    clause_text = value.strip()
    expected_heading = _CLAUSE_HEADINGS[key]
    if not clause_text.startswith(expected_heading):
        return None

    if clause_text in {expected_heading, f"{expected_heading}\n\n"}:
        return None

    if any(marker in clause_text for marker in _TEMPLATE_MARKERS):
        return None

    return clause_text


def _log_clause_payload_warning(event: str, raw_text: str, **extra: Any) -> None:
    logger.warning(
        event,
        raw_text_preview=raw_text[:_RAW_TEXT_LOG_LIMIT],
        **extra,
    )
