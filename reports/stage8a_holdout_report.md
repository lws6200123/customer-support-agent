# Stage 8A Post-fix Holdout Sanity Check

This holdout was created and frozen after the Stage 8A fixes and was not used for subsequent system tuning.

## Configuration

- Run: `HOLDOUT_RUN_1`
- Cases: 24
- Holdout SHA256: `0eb3da3ef0b8012a3f69c06a938d5f87152092ae1fe481a3cc273774dd1c9252`
- Frozen system commit: `15dd755502548ba6899a752b5298d6d8ba355517`
- DeepSeek model: `deepseek-v4-flash`
- Execution: sequential, real DeepSeek + RAGFlow + frozen LangGraph + real tools
- Runtime: isolated disposable evaluation SQLite database
- Post-result tuning or rerun: prohibited

## Distribution

- Intent: `{'ACCOUNT': 3, 'DELIVERY': 4, 'INVOICE': 3, 'OTHER': 4, 'PRODUCT_AFTER_SALES': 4, 'RETURN_REFUND': 6}`
- Decision: `{'AUTO_RESOLVE': 13, 'ESCALATE_TO_HUMAN': 6, 'NEED_MORE_INFO': 5}`
- Escalation-critical: 6
- Information-missing: 5

## Metrics

- Intent Accuracy: 100.00% (24/24)
- Decision Accuracy: 95.83% (23/24)
- Task Success Rate: 95.83% (23/24)
- Escalation Precision / Recall / F1: 100.00% / 83.33% / 90.91%
- Tool Precision / Recall / F1: 100.00% / 100.00% / 100.00%
- Exact Tool Set Accuracy: 100.00%
- Average Tool Calls: 2.4
- System Error Rate: 0.00% (0/24)

## Latency

- Mean: 23762.8 ms
- P50: 19736.9 ms
- P95: 40092.5 ms
- Min: 7173.7 ms
- Max: 54061.9 ms

## Failed Cases

### HOLD-REF-003

- Expected: `RETURN_REFUND` / `ESCALATE_TO_HUMAN`
- Actual: `RETURN_REFUND` / `NEED_MORE_INFO`
- Tool sequence: `['lookup_customer', 'lookup_order', 'search_knowledge', 'evaluate_refund']`
- Primary / secondary: `DECISION_ERROR` / `['MISSING_INFO_ROUTING_ERROR']`
- Error codes: `[]`
- Safety risk: yes
- Observed classification detail: `sub_intent=request_refund`; no `reason_code` was extracted.
- Deterministic consequence: `RefundDecisionService` requested `reason_code` before it could apply the over-500-BRL automatic-control escalation.
- Retrieval and tools: all required tools ran, knowledge retrieval succeeded, and no system error occurred.
- Post-result action: recorded only; no system, prompt, rule, or holdout change was made.

## Missed Escalation

- `HOLD-REF-003` expected escalation but predicted `NEED_MORE_INFO`.

## Difference from the 60-case Benchmark

The 60-case benchmark was created before the Stage 8A official runs and was used to identify generalizable implementation defects. This 24-case holdout was authored only after those fixes, uses new messages, is smaller, and is a one-shot sanity check. It does not replace the main benchmark, increase its sample size, or justify production claims.

## Statistical Boundary

This is a controlled one-shot portfolio holdout against one configured model and knowledge dataset. It is not production traffic, a production SLA, an industry benchmark, or an independently labeled test set.
