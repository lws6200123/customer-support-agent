"""Stage 3 policy metadata, rule, taxonomy, and example consistency tests."""

from __future__ import annotations

from pathlib import Path

from scripts.audit_policies import (
    EXPECTED_DECISIONS,
    EXPECTED_INTENTS,
    EXPECTED_POLICY_FILES,
    REQUIRED_METADATA,
    SIMULATED_NOTICE,
    audit_policy_repository,
    evaluate_example,
    load_yaml,
    parse_policy_document,
    resolve_reference,
)


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
POLICIES = KNOWLEDGE / "policies"


def _documents():
    return [parse_policy_document(POLICIES / name) for name in EXPECTED_POLICY_FILES]


def test_all_policy_metadata_is_valid() -> None:
    documents = _documents()
    assert len(documents) == 10
    for metadata, _ in documents:
        assert REQUIRED_METADATA <= set(metadata)
        assert metadata["status"] in {"draft", "active", "deprecated"}
        assert metadata["source_type"] in {"public_policy_derived", "simulated_internal"}
        assert isinstance(metadata["topics"], list) and metadata["topics"]


def test_document_ids_are_unique() -> None:
    document_ids = [metadata["document_id"] for metadata, _ in _documents()]
    assert len(document_ids) == len(set(document_ids))


def test_public_source_references_are_valid_and_official() -> None:
    sources = load_yaml(KNOWLEDGE / "sources.yaml")["sources"]
    source_map = {source["source_id"]: source for source in sources}
    assert len(source_map) == 9
    for source in sources:
        assert source["url"].startswith("https://help.jd.com/")
        assert source["access_status"] in {"accessible", "inaccessible"}
    for metadata, _ in _documents():
        if metadata["source_type"] == "public_policy_derived":
            assert metadata["source_ids"]
            assert set(metadata["source_ids"]) <= set(source_map)
            for source_id in metadata["source_ids"]:
                assert metadata["document_id"] in source_map[source_id]["used_by_documents"]


def test_simulated_labeling_is_enforced() -> None:
    simulated = 0
    for metadata, body in _documents():
        if metadata["source_type"] == "simulated_internal":
            simulated += 1
            normalized = "\n".join(line.rstrip() for line in body.lstrip().splitlines()[:2])
            assert normalized == SIMULATED_NOTICE
    assert simulated == 4


def test_business_rule_schema_and_references_are_valid() -> None:
    rules = load_yaml(KNOWLEDGE / "business_rules.yaml")
    simulation = rules["simulation_business"]
    assert simulation["currency"] == "CNY_EQUIVALENT"
    assert simulation["auto_refund_limit"] > 0
    assert simulation["refund_frequency_window_days"] > 0
    assert simulation["max_auto_refunds_in_window"] > 0
    for group in (rules["refund_rules"]["auto_approval_candidate_conditions"], rules["escalation_rules"]):
        for item in group:
            for condition in item.get("all", [item]):
                if "value_ref" in condition:
                    assert resolve_reference(rules, condition["value_ref"]) is not None


def test_sla_values_are_positive_and_priority_ordered() -> None:
    sla = load_yaml(KNOWLEDGE / "business_rules.yaml")["sla"]
    values = [sla[level]["response_minutes"] for level in ("low", "normal", "high", "urgent")]
    assert all(isinstance(value, int) and value > 0 for value in values)
    assert values[0] > values[1] > values[2] > values[3]


def test_decision_enum_is_canonical() -> None:
    rules = load_yaml(KNOWLEDGE / "business_rules.yaml")
    assert set(rules["decisions"]) == EXPECTED_DECISIONS
    assert len(rules["decisions"]) == len(set(rules["decisions"]))
    assert set(rules["decision_precedence"]) == EXPECTED_DECISIONS


def test_intent_taxonomy_is_fixed_and_has_no_duplicate_sub_intents() -> None:
    intents = load_yaml(KNOWLEDGE / "intent_taxonomy.yaml")["top_level_intents"]
    assert set(intents) == EXPECTED_INTENTS
    sub_intents = [sub_intent for values in intents.values() for sub_intent in values]
    assert len(sub_intents) == len(set(sub_intents))
    assert all(values for values in intents.values())


def test_decision_examples_match_canonical_rules() -> None:
    rules = load_yaml(KNOWLEDGE / "business_rules.yaml")
    examples = load_yaml(KNOWLEDGE / "decision_examples.yaml")["examples"]
    assert 15 <= len(examples) <= 20
    assert len({example["example_id"] for example in examples}) == len(examples)
    for example in examples:
        assert example["expected_decision"] in EXPECTED_DECISIONS
        assert evaluate_example(example, rules) == example["expected_decision"]


def test_full_policy_conflict_audit_passes() -> None:
    result = audit_policy_repository(ROOT)
    assert result["passed"], result["errors"]
    assert result["shadow_threshold_count"] == 0
    assert result["decision_example_mismatches"] == []
