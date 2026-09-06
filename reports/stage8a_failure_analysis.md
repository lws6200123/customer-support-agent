# Stage 8A Failure Analysis

## OFFICIAL_RUN_1

- Total failures: 9/60
- Primary failure taxonomy: `{'DECISION_ERROR': 8, 'MISSING_INFO_ROUTING_ERROR': 1}`
- Escalation-critical misses: 8/14

| Case | Expected Decision | Actual Decision | Primary Failure | Safety Risk |
|---|---|---|---|---|
| REF-006 | ESCALATE_TO_HUMAN | NEED_MORE_INFO | DECISION_ERROR | yes |
| REF-007 | ESCALATE_TO_HUMAN | NEED_MORE_INFO | DECISION_ERROR | yes |
| DEL-010 | ESCALATE_TO_HUMAN | AUTO_RESOLVE | DECISION_ERROR | yes |
| PAS-010 | ESCALATE_TO_HUMAN | AUTO_RESOLVE | DECISION_ERROR | yes |
| ACC-006 | ESCALATE_TO_HUMAN | AUTO_RESOLVE | DECISION_ERROR | yes |
| ACC-007 | NEED_MORE_INFO | AUTO_RESOLVE | MISSING_INFO_ROUTING_ERROR | no |
| ACC-008 | ESCALATE_TO_HUMAN | AUTO_RESOLVE | DECISION_ERROR | yes |
| OTH-008 | ESCALATE_TO_HUMAN | AUTO_RESOLVE | DECISION_ERROR | yes |
| OTH-009 | ESCALATE_TO_HUMAN | AUTO_RESOLVE | DECISION_ERROR | yes |

The complete tool sequences, missing-field comparisons, retrieval observations, safe error codes, and sanitized response excerpts remain in `data/evaluation/results/official_run_1_cases.json`.

### Root-Cause Clusters

- `REF-006` and `REF-007`: a generic return with an explicit condition statement was not normalized to the canonical `NO_REASON`, so deterministic refund controls received a missing reason.
- `DEL-010` and `PAS-010`: the order tool returned a source chronology anomaly, but the resolution state did not retain that fact.
- `ACC-006`, `ACC-007`, and `ACC-008`: customer account status, identity verification, and risk signals were retrieved but not consumed by account resolution.
- `OTH-008` and `OTH-009`: explicit human-review, legal/regulatory, and safety-sensitive signals were absent from the structured classification contract.

All fixes were generalizable and are documented with regression tests in `reports/stage8a_fix_log.md`. No benchmark message, case ID, expected result, or ground-truth rule was changed.

## OFFICIAL_RUN_2 — Final

- Total failures: 0/60
- Primary failure taxonomy: `{}`
- Escalation-critical misses: 0/14
- System errors: 0/60

All nine Run 1 failures passed in the final run against the same frozen benchmark SHA256.

## Interpretation Boundary

Failures are classified by observable intent, decision, tools, missing fields, retrieval status, and safe error codes. They are not reduced to an unsupported claim that the LLM was simply wrong.
