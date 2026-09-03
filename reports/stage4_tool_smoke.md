# Stage 4 Business Tool Smoke

## Scope

The six structured tools were exercised without an LLM. Business mutations ran against a disposable SQLite database; the configured RAGFlow dataset was queried read-only.

## Result

- Passed: 14/14
- Simulation clock: `2026-09-03T12:00:00`
- Currency: `BRL`
- Secrets and dataset identifiers are intentionally omitted

| Case | Check | Status | Evidence |
|---|---|---:|---|
| TS-01 | valid customer | PASS | customer context returned |
| TS-02 | missing customer | PASS | error_code=CUSTOMER_NOT_FOUND |
| TS-03 | normal order | PASS | complete order context returned |
| TS-04 | multi-item order | PASS | order=ORD-000004; items_rows=4 |
| TS-05 | multi-payment order | PASS | order=ORD-000010; payments_rows=2 |
| TS-06 | delivered-late order | PASS | order=ORD-000017; items_rows=1 |
| TS-07 | refund auto-resolve candidate | PASS | decision=AUTO_RESOLVE; eligible=True |
| TS-08 | refund risk escalation | PASS | decision=ESCALATE_TO_HUMAN; reason=RISK_FLAGGED |
| TS-09 | refund amount escalation | PASS | decision=ESCALATE_TO_HUMAN; amount=501 BRL |
| TS-10 | refund need-more-info | PASS | missing_fields=['product_condition_ok'] |
| TS-11 | create/read/update ticket | PASS | ticket lifecycle completed; final_status=resolved |
| TS-12 | valid KnowledgeTool retrieval | PASS | top3=['POL-RETURN-001', 'POL-RETURN-001', 'POL-AFTERSALES-002'] |
| TS-13 | KnowledgeTool weak evidence | PASS | error_code=POLICY_EVIDENCE_NOT_FOUND |
| TS-14 | source-quality anomaly escalation | PASS | decision=ESCALATE_TO_HUMAN; reason=SOURCE_DATA_QUALITY_ANOMALY |

## Interpretation

`AUTO_RESOLVE` is only a deterministic automation candidate; this stage does not execute refunds or implement an Agent. The weak-evidence check verifies a safe structured outcome and does not establish a calibrated relevance threshold.
