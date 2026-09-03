#!/usr/bin/env python3
"""Deterministically audit Stage 3 policy structure and rule consistency."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
POLICY_DIR = KNOWLEDGE_DIR / "policies"
REPORT_PATH = PROJECT_ROOT / "reports" / "stage3_policy_audit.md"

EXPECTED_POLICY_FILES = tuple(f"{index:02d}_{name}.md" for index, name in enumerate(
    (
        "return_exchange_policy",
        "product_after_sales_policy",
        "shipping_delivery_policy",
        "refund_processing_policy",
        "invoice_policy",
        "account_security_policy",
        "customer_service_sla",
        "manual_escalation_policy",
        "refund_risk_control",
        "customer_support_operations",
    ),
    start=1,
))
REQUIRED_METADATA = {
    "document_id",
    "title",
    "document_type",
    "source_type",
    "source_organization",
    "version",
    "status",
    "effective_date",
    "language",
    "topics",
}
VALID_SOURCE_TYPES = {"public_policy_derived", "simulated_internal"}
VALID_STATUSES = {"draft", "active", "deprecated"}
EXPECTED_INTENTS = {
    "RETURN_REFUND",
    "DELIVERY",
    "PRODUCT_AFTER_SALES",
    "ACCOUNT",
    "INVOICE",
    "OTHER",
}
EXPECTED_DECISIONS = {"AUTO_RESOLVE", "NEED_MORE_INFO", "ESCALATE_TO_HUMAN"}
SIMULATED_NOTICE = "SIMULATED INTERNAL POLICY\nFor portfolio demonstration only."


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def parse_policy_document(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path.name}: missing or malformed YAML frontmatter")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError(f"{path.name}: frontmatter must be a mapping")
    return metadata, match.group(2)


def resolve_reference(rules: dict[str, Any], reference: str) -> Any:
    value: Any = rules
    for part in reference.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(reference)
        value = value[part]
    return value


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    operations = {
        "equals": lambda: actual == expected,
        "not_equals": lambda: actual != expected,
        "less_than": lambda: actual < expected,
        "less_than_or_equal": lambda: actual <= expected,
        "greater_than": lambda: actual > expected,
        "greater_than_or_equal": lambda: actual >= expected,
    }
    if operator not in operations:
        raise ValueError(f"Unknown rule operator: {operator}")
    return bool(operations[operator]())


def condition_matches(condition: dict[str, Any], facts: dict[str, Any], rules: dict[str, Any]) -> bool:
    if "all" in condition:
        return all(condition_matches(item, facts, rules) for item in condition["all"])
    field = condition["field"]
    if field not in facts:
        return False
    expected = (
        resolve_reference(rules, condition["value_ref"])
        if "value_ref" in condition
        else condition.get("value")
    )
    return _compare(facts[field], condition["operator"], expected)


def evaluate_example(example: dict[str, Any], rules: dict[str, Any]) -> str:
    facts = example.get("facts", {})
    for escalation in rules["escalation_rules"]:
        if condition_matches(escalation, facts, rules):
            return "ESCALATE_TO_HUMAN"
    if example.get("missing_fields") or facts.get("information_complete") is False:
        return "NEED_MORE_INFO"
    if example.get("action_type") == rules["refund_rules"]["action_type"]:
        conditions = rules["refund_rules"]["auto_approval_candidate_conditions"]
        return (
            rules["refund_rules"]["eligible_decision"]
            if all(condition_matches(item, facts, rules) for item in conditions)
            else rules["refund_rules"]["otherwise_decision"]
        )
    return "AUTO_RESOLVE"


def audit_policy_repository(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    knowledge = root / "knowledge"
    policy_dir = knowledge / "policies"
    errors: list[str] = []
    warnings: list[str] = []
    policies: list[dict[str, Any]] = []

    actual_names = tuple(sorted(path.name for path in policy_dir.glob("*.md")))
    if set(actual_names) != set(EXPECTED_POLICY_FILES):
        errors.append(
            f"Policy file set differs: missing={sorted(set(EXPECTED_POLICY_FILES) - set(actual_names))}, "
            f"extra={sorted(set(actual_names) - set(EXPECTED_POLICY_FILES))}"
        )
    for path in sorted(policy_dir.glob("*.md")):
        try:
            metadata, body = parse_policy_document(path)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))
            continue
        missing = sorted(REQUIRED_METADATA - set(metadata))
        if missing:
            errors.append(f"{path.name}: missing metadata {missing}")
        if metadata.get("status") not in VALID_STATUSES:
            errors.append(f"{path.name}: invalid status {metadata.get('status')!r}")
        if metadata.get("source_type") not in VALID_SOURCE_TYPES:
            errors.append(f"{path.name}: invalid source_type {metadata.get('source_type')!r}")
        if not isinstance(metadata.get("topics"), list) or not metadata.get("topics"):
            errors.append(f"{path.name}: topics must be a non-empty list")
        normalized_start = "\n".join(line.rstrip() for line in body.lstrip().splitlines()[:2])
        if metadata.get("source_type") == "simulated_internal" and normalized_start != SIMULATED_NOTICE:
            errors.append(f"{path.name}: simulated-policy notice missing at body start")
        if metadata.get("source_type") == "public_policy_derived" and not metadata.get("source_ids"):
            errors.append(f"{path.name}: public-derived policy has no source_ids")
        policies.append({"path": path, "metadata": metadata, "body": body})

    document_ids = [item["metadata"].get("document_id") for item in policies]
    duplicate_document_ids = sorted({value for value in document_ids if document_ids.count(value) > 1})
    if duplicate_document_ids:
        errors.append(f"Duplicate document_id values: {duplicate_document_ids}")

    sources = load_yaml(knowledge / "sources.yaml").get("sources", [])
    source_ids = [source.get("source_id") for source in sources]
    if len(source_ids) != len(set(source_ids)):
        errors.append("sources.yaml contains duplicate source_id values")
    source_map = {source.get("source_id"): source for source in sources}
    required_source_fields = {
        "source_id", "organization", "title", "url", "source_type",
        "retrieved_or_reviewed_date", "used_by_documents", "notes", "access_status",
    }
    for source in sources:
        missing = sorted(required_source_fields - set(source))
        if missing:
            errors.append(f"Source {source.get('source_id')}: missing fields {missing}")
        if not str(source.get("url", "")).startswith("https://help.jd.com/"):
            errors.append(f"Source {source.get('source_id')}: URL is not official help.jd.com")
        if source.get("access_status") not in {"accessible", "inaccessible"}:
            errors.append(f"Source {source.get('source_id')}: invalid access_status")

    for policy in policies:
        metadata = policy["metadata"]
        for source_id in metadata.get("source_ids", []):
            if source_id not in source_map:
                errors.append(f"{policy['path'].name}: unknown source_id {source_id}")
            elif metadata.get("document_id") not in source_map[source_id].get("used_by_documents", []):
                errors.append(f"{policy['path'].name}: source {source_id} lacks reciprocal used_by_documents entry")

    rules = load_yaml(knowledge / "business_rules.yaml")
    simulation = rules.get("simulation_business", {})
    numeric_fields = ("auto_refund_limit", "refund_frequency_window_days", "max_auto_refunds_in_window")
    for field in numeric_fields:
        value = simulation.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            errors.append(f"business_rules.yaml: simulation_business.{field} must be positive")
    if not isinstance(simulation.get("currency"), str) or not simulation.get("currency"):
        errors.append("business_rules.yaml: simulation_business.currency is required")
    decisions = rules.get("decisions", [])
    if set(decisions) != EXPECTED_DECISIONS or len(decisions) != len(set(decisions)):
        errors.append("business_rules.yaml: decision enum must contain each canonical decision once")
    sla = rules.get("sla", {})
    if set(sla) != {"low", "normal", "high", "urgent"}:
        errors.append("business_rules.yaml: SLA priorities must be low/normal/high/urgent")
    else:
        values = [sla[level].get("response_minutes") for level in ("low", "normal", "high", "urgent")]
        if not all(isinstance(value, int) and value > 0 for value in values):
            errors.append("business_rules.yaml: SLA response_minutes values must be positive integers")
        elif not (values[0] > values[1] > values[2] > values[3]):
            errors.append("business_rules.yaml: SLA response targets have conflicting priority order")

    rule_references: list[str] = []
    for section in (rules.get("refund_rules", {}).get("auto_approval_candidate_conditions", []), rules.get("escalation_rules", [])):
        for item in section:
            nested = item.get("all", [item])
            for condition in nested:
                if "value_ref" in condition:
                    rule_references.append(condition["value_ref"])
    for reference in rule_references:
        try:
            resolve_reference(rules, reference)
        except KeyError:
            errors.append(f"business_rules.yaml: unresolved value_ref {reference}")
    escalation_ids = [item.get("rule_id") for item in rules.get("escalation_rules", [])]
    if len(escalation_ids) != len(set(escalation_ids)):
        errors.append("business_rules.yaml: duplicate escalation rule IDs")

    # Numeric operational thresholds must not be copied into prose and become a
    # second source of truth. Public/source titles live in sources.yaml instead.
    threshold_pattern = re.compile(
        r"(?i)(?:CNY|RMB|yuan|refund limit|response target|refund frequency).{0,40}\b\d+(?:\.\d+)?"
    )
    shadow_thresholds = []
    for policy in policies:
        for match in threshold_pattern.finditer(policy["body"]):
            shadow_thresholds.append(f"{policy['path'].name}: {match.group(0)!r}")
    if shadow_thresholds:
        errors.append(f"Policy prose contains shadow numeric thresholds: {shadow_thresholds}")

    taxonomy = load_yaml(knowledge / "intent_taxonomy.yaml")
    intents = taxonomy.get("top_level_intents", {})
    if set(intents) != EXPECTED_INTENTS:
        errors.append("intent_taxonomy.yaml: top-level intent set is not the fixed V1 taxonomy")
    sub_intents: list[str] = []
    for intent, values in intents.items():
        if not isinstance(values, list) or not values:
            errors.append(f"intent_taxonomy.yaml: {intent} must have a non-empty sub-intent list")
        else:
            sub_intents.extend(values)
    duplicates = sorted({value for value in sub_intents if sub_intents.count(value) > 1})
    if duplicates:
        errors.append(f"intent_taxonomy.yaml: duplicate sub-intents {duplicates}")

    example_data = load_yaml(knowledge / "decision_examples.yaml")
    examples = example_data.get("examples", [])
    if not 15 <= len(examples) <= 20:
        errors.append("decision_examples.yaml: expected 15 to 20 examples")
    example_ids = [example.get("example_id") for example in examples]
    if len(example_ids) != len(set(example_ids)):
        errors.append("decision_examples.yaml: duplicate example_id values")
    decision_mismatches: list[str] = []
    for example in examples:
        intent = example.get("intent")
        sub_intent = example.get("sub_intent")
        if intent not in intents:
            errors.append(f"{example.get('example_id')}: unknown intent {intent}")
        elif sub_intent not in intents[intent]:
            errors.append(f"{example.get('example_id')}: invalid sub-intent {sub_intent} for {intent}")
        if example.get("expected_decision") not in decisions:
            errors.append(f"{example.get('example_id')}: invalid expected decision")
            continue
        actual = evaluate_example(example, rules)
        if actual != example.get("expected_decision"):
            decision_mismatches.append(
                f"{example.get('example_id')}: expected {example.get('expected_decision')}, calculated {actual}"
            )
    errors.extend(decision_mismatches)

    public_count = sum(item["metadata"].get("source_type") == "public_policy_derived" for item in policies)
    simulated_count = sum(item["metadata"].get("source_type") == "simulated_internal" for item in policies)
    if (public_count, simulated_count) != (6, 4):
        errors.append(f"Expected 6 public-derived and 4 simulated policies; found {public_count} and {simulated_count}")
    inaccessible = [source["source_id"] for source in sources if source.get("access_status") == "inaccessible"]
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "policy_count": len(policies),
        "public_policy_derived_count": public_count,
        "simulated_internal_count": simulated_count,
        "source_count": len(sources),
        "accessible_source_count": len(sources) - len(inaccessible),
        "inaccessible_sources": inaccessible,
        "decision_example_count": len(examples),
        "decision_example_mismatches": decision_mismatches,
        "shadow_threshold_count": len(shadow_thresholds),
        "document_ids": document_ids,
    }


def render_report(result: dict[str, Any]) -> str:
    outcome = "PASS" if result["passed"] else "FAIL"
    lines = [
        "# Stage 3 Policy Audit",
        "",
        f"**Overall result: {outcome}**",
        "",
        "## Scope",
        "",
        "DemoShop is a portfolio simulation. Anonymized Olist transactional records and public "
        "policy references come from different sources and are not claimed to belong to the same real company.",
        "",
        "## Inventory",
        "",
        f"- Policy documents: {result['policy_count']}",
        f"- Public-policy-derived: {result['public_policy_derived_count']}",
        f"- Simulated internal: {result['simulated_internal_count']}",
        f"- Registered official sources: {result['source_count']}",
        f"- Accessible and reviewed sources: {result['accessible_source_count']}",
        f"- Inaccessible sources: {result['inaccessible_sources'] or 'none'}",
        f"- Decision examples: {result['decision_example_count']}",
        "",
        "## Deterministic checks",
        "",
        "- Required frontmatter and valid metadata enums",
        "- Unique document and source identifiers",
        "- Public source references and reciprocal registry usage",
        "- Mandatory simulated-policy disclosure",
        "- Positive canonical business thresholds and ordered SLA values",
        "- Resolvable rule references and unique escalation IDs",
        "- Fixed six-intent V1 taxonomy with unique sub-intents",
        "- Decision examples recalculated from canonical rules",
        "- No numeric operational threshold shadowed in Markdown prose",
        "",
        "## Conflict findings",
        "",
        f"- Decision mismatches: {len(result['decision_example_mismatches'])}",
        f"- Shadow numeric thresholds: {result['shadow_threshold_count']}",
        f"- Structural or rule errors: {len(result['errors'])}",
    ]
    if result["errors"]:
        lines.extend(["", "### Errors", ""] + [f"- {error}" for error in result["errors"]])
    else:
        lines.extend(
            [
                "",
                "No deterministic structural conflict was detected. This audit cannot prove legal "
                "correctness or resolve every semantic ambiguity; those remain human-review concerns.",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    result = audit_policy_repository(args.root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(result), encoding="utf-8")
    print(
        f"Stage 3 policy audit: {'PASS' if result['passed'] else 'FAIL'}; "
        f"policies={result['policy_count']}, examples={result['decision_example_count']}"
    )
    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
