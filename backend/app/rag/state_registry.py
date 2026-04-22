from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractStateContext:
    state_name: str
    sale_proceeding: str
    surplus_statute: str
    typical_timeline: str

    def to_prompt_context(self) -> dict[str, str]:
        return {
            "state_name": self.state_name,
            "sale_proceeding": self.sale_proceeding,
            "surplus_statute": self.surplus_statute,
            "typical_timeline": self.typical_timeline,
        }


@dataclass(frozen=True)
class StateRegistryEntry:
    code: str
    contract_template: str
    contract_context: ContractStateContext
    letter_template: str | None = None


DEFAULT_STATE = "FL"

STATE_REGISTRY: dict[str, StateRegistryEntry] = {
    "FL": StateRegistryEntry(
        code="FL",
        contract_template="fl_recovery_agreement.j2",
        contract_context=ContractStateContext(
            state_name="Florida",
            sale_proceeding="tax deed sale",
            surplus_statute="Fla. Stat. § 197.582",
            typical_timeline="60 to 120 days",
        ),
        letter_template=None,
    ),
    "CA": StateRegistryEntry(
        code="CA",
        contract_template="ca_recovery_agreement.j2",
        contract_context=ContractStateContext(
            state_name="California",
            sale_proceeding="tax-defaulted property sale",
            surplus_statute="Cal. Rev. & Tax. Code § 4675",
            typical_timeline="90 to 180 days",
        ),
        letter_template="california_excess_proceeds.j2",
    ),
    "GA": StateRegistryEntry(
        code="GA",
        contract_template="ga_recovery_agreement.j2",
        contract_context=ContractStateContext(
            state_name="Georgia",
            sale_proceeding="tax sale",
            surplus_statute="O.C.G.A. § 48-4-5",
            typical_timeline="90 to 180 days",
        ),
        letter_template="georgia_excess_proceeds.j2",
    ),
    "TX": StateRegistryEntry(
        code="TX",
        contract_template="tx_recovery_agreement.j2",
        contract_context=ContractStateContext(
            state_name="Texas",
            sale_proceeding="tax sale",
            surplus_statute="Tex. Tax Code §§ 34.03 and 34.04",
            typical_timeline="90 to 180 days",
        ),
        letter_template="texas_excess_proceeds.j2",
    ),
    "OH": StateRegistryEntry(
        code="OH",
        contract_template="oh_recovery_agreement.j2",
        contract_context=ContractStateContext(
            state_name="Ohio",
            sale_proceeding="tax foreclosure sale",
            surplus_statute="Ohio Rev. Code § 5721.20",
            typical_timeline="90 to 180 days",
        ),
        letter_template="ohio_excess_proceeds.j2",
    ),
}

CONTRACT_TEMPLATE_MAP: dict[str, str] = {
    code: entry.contract_template for code, entry in STATE_REGISTRY.items()
}

LETTER_TEMPLATE_MAP: dict[str, str] = {
    code: entry.letter_template
    for code, entry in STATE_REGISTRY.items()
    if entry.letter_template is not None
}

STATE_CONTEXT: dict[str, ContractStateContext] = {
    code: entry.contract_context for code, entry in STATE_REGISTRY.items()
}


def get_state_registry_entry(state: str | None) -> StateRegistryEntry | None:
    if not state:
        return None
    return STATE_REGISTRY.get(state.strip().upper())
