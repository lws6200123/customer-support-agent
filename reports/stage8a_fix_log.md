# Stage 8A Fix Log

## Baseline

- Run: `OFFICIAL_RUN_1`
- Frozen benchmark SHA256: `258400c7fb9bddab2ebc742553b67d3c21bdd5cef50d76f15689c1544419ad10`
- Result: 51/60 task success (85.00%)
- Safety result: 6/14 escalation-critical cases correctly escalated
- System errors: 0/60

The benchmark file and its ground truth were not changed after the audit passed.

## Issue 1: Generic return reason was dropped

- Before: a generic `return_product` classification with an explicit item-condition statement but no special defect/damage reason sent `reason_code=null` to the deterministic refund service. The service correctly requested `reason_code`, preventing customer risk and account controls from determining the final decision.
- Root cause: the workflow did not map a generic-condition return to the canonical `NO_REASON` rule value.
- Fix: normalize only `return_product` requests that contain an explicit product-condition fact and no special reason to `NO_REASON` before invoking `evaluate_refund`.
- Regression: `test_generic_return_normalizes_no_special_reason`.

## Issue 2: Retrieved control facts did not reach resolution

- Before: customer risk, account status, identity verification, and order source-quality facts were returned by tools but reduced to display-only summaries. Non-refund resolution therefore could not enforce those controls.
- Root cause: the guarded state retained tool metadata but not the small set of typed control facts required by deterministic routing.
- Fix: propagate the four typed control facts in transient Agent state. Source-data anomalies and risky/inactive accounts route to human review; sensitive account actions without verified identity request identity verification.
- Regressions: `test_non_refund_source_data_anomaly_escalates` and `test_account_control_facts_drive_resolution`.

## Issue 3: Explicit safety escalation signals had no contract

- Before: explicit requests for human review, legal/regulatory complaints, and personal-safety-sensitive messages could be classified correctly as `OTHER` but then fell through to `AUTO_RESOLVE`.
- Root cause: the structured classification contract did not expose these routing signals to the deterministic graph.
- Fix: add three general semantic booleans to the structured classification schema and deterministically route any asserted signal to human review.
- Regression: `test_explicit_escalation_signals_route_to_human`.

## Issue 4: Failure taxonomy included successful expected-not-found paths

- Before: correct missing-information cases with an expected failed lookup were marked successful but also counted as `TOOL_ERROR` in aggregate taxonomy.
- Root cause: failure classification was applied to every case, rather than only cases that failed the frozen task-success contract. The evaluator also did not explicitly exclude system errors from task success.
- Fix: successful cases have no failure taxonomy entry, and any system error makes task success false.
- Regressions: `test_expected_not_found_tool_result_is_not_a_failure_category` and `test_system_error_cannot_count_as_task_success`.

## Scope and Integrity

- No case ID, exact benchmark message, or benchmark-specific branch was added to runtime code.
- No policy threshold, RAG setting, business-rule file, or ground-truth field was modified.
- `OFFICIAL_RUN_1` case outcomes remain 51/60; only its aggregate failure taxonomy was corrected from an internally inconsistent count to 8 `DECISION_ERROR` and 1 `MISSING_INFO_ROUTING_ERROR`.
- A second full official run is required to measure the implementation changes against the unchanged benchmark.
