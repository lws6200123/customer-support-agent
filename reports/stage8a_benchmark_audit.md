# Stage 8A Benchmark Audit

**Status: PASS**

- Cases: 60
- Intent distribution: `{'ACCOUNT': 8, 'DELIVERY': 10, 'INVOICE': 8, 'OTHER': 9, 'PRODUCT_AFTER_SALES': 10, 'RETURN_REFUND': 15}`
- Decision distribution: `{'AUTO_RESOLVE': 31, 'ESCALATE_TO_HUMAN': 14, 'NEED_MORE_INFO': 15}`
- Escalation-critical cases: 14
- Information-missing cases: 15
- Benchmark SHA256: `258400c7fb9bddab2ebc742553b67d3c21bdd5cef50d76f15689c1544419ad10`
- Evaluation DB: rebuilt from processed data and isolated from the Demo runtime
- Refund decisions: recomputed with `RefundDecisionService`
- Identifier, taxonomy, tool-set, enum, conflict, and credential checks: completed

## Ground Truth Sources

1. Stage 2 SQLite facts and scenario labels.
2. Canonical `knowledge/business_rules.yaml` and `knowledge/decision_examples.yaml`.
3. Deterministic `RefundDecisionService` for every refund case.
4. Human-reviewed intent, tool, missing-information, legal, safety, and routing expectations.
5. An explicitly declared evaluation-only synthetic refund-frequency fixture.

## Errors

No audit errors.

## Statistical Boundary

This is a 60-case controlled portfolio benchmark, not production traffic, a production SLA, or an industry benchmark.
