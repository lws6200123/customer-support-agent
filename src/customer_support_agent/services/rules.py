"""Load canonical Stage 3 business rules without duplicating thresholds in Python."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from customer_support_agent.core.config import PROJECT_ROOT
from customer_support_agent.core.errors import InvalidInputError


BUSINESS_RULES_PATH = PROJECT_ROOT / "knowledge" / "business_rules.yaml"
INTENT_TAXONOMY_PATH = PROJECT_ROOT / "knowledge" / "intent_taxonomy.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise InvalidInputError(f"Canonical configuration is not a mapping: {path.name}")
    return value


@lru_cache(maxsize=1)
def load_business_rules() -> dict[str, Any]:
    rules = _load_yaml(BUSINESS_RULES_PATH)
    required = {
        "simulation_business",
        "currency_semantics",
        "refund_frequency_semantics",
        "refund_rules",
        "escalation_rules",
        "ticket_operations",
        "decisions",
    }
    missing = sorted(required - set(rules))
    if missing:
        raise InvalidInputError(f"Canonical business rules are missing: {missing}")
    return rules


@lru_cache(maxsize=1)
def load_intent_taxonomy() -> dict[str, list[str]]:
    taxonomy = _load_yaml(INTENT_TAXONOMY_PATH).get("top_level_intents")
    if not isinstance(taxonomy, dict):
        raise InvalidInputError("Intent taxonomy is missing top_level_intents")
    return taxonomy


def resolve_rule_reference(rules: dict[str, Any], reference: str) -> Any:
    value: Any = rules
    for part in reference.split("."):
        if not isinstance(value, dict) or part not in value:
            raise InvalidInputError(f"Unresolved canonical rule reference: {reference}")
        value = value[part]
    return value
