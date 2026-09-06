# Stage 8A Agent Benchmark

## Benchmark Configuration

- Official run: `OFFICIAL_RUN_1`
- Cases: 60
- Benchmark SHA256: `258400c7fb9bddab2ebc742553b67d3c21bdd5cef50d76f15689c1544419ad10`
- Git commit: `b832102d8ce8de4c885b688d8237f5bcd23cad64`
- DeepSeek model: `deepseek-v4-flash`
- Business rules version: `1.0.0`
- Simulation clock: `2026-09-03T12:00:00`
- Execution: sequential, real DeepSeek + RAGFlow + LangGraph + Stage 4 tools
- Runtime: isolated disposable evaluation SQLite database

## Dataset Distribution

- Intent: `{'ACCOUNT': 8, 'DELIVERY': 10, 'INVOICE': 8, 'OTHER': 9, 'PRODUCT_AFTER_SALES': 10, 'RETURN_REFUND': 15}`
- Decision: `{'AUTO_RESOLVE': 31, 'ESCALATE_TO_HUMAN': 14, 'NEED_MORE_INFO': 15}`
- Escalation-critical: 14

## Overall Metrics

- Intent Accuracy: 100.00% (60/60)
- Decision Accuracy: 85.00% (51/60)
- Task Success Rate: 85.00% (51/60)
- Exact Tool Set Accuracy: 100.00%
- Failure Count: 9
- System Error Rate: 0.00% (0/60)

## Per-Intent Accuracy

| Intent | Correct | Total | Accuracy |
|---|---:|---:|---:|
| ACCOUNT | 8 | 8 | 100.00% |
| DELIVERY | 10 | 10 | 100.00% |
| INVOICE | 8 | 8 | 100.00% |
| OTHER | 9 | 9 | 100.00% |
| PRODUCT_AFTER_SALES | 10 | 10 | 100.00% |
| RETURN_REFUND | 15 | 15 | 100.00% |

## Decision Metrics

| Decision | Correct | Total | Accuracy |
|---|---:|---:|---:|
| AUTO_RESOLVE | 31 | 31 | 100.00% |
| NEED_MORE_INFO | 14 | 15 | 93.33% |
| ESCALATE_TO_HUMAN | 6 | 14 | 42.86% |

## Safety Metrics

- Escalation Precision: 100.00%
- Escalation Recall: 42.86%
- Escalation F1: 60.00%
- Correctly escalated critical cases: 6/14
- Missed critical escalations: 8

## Tool Metrics

- Tool Selection Precision: 100.00%
- Tool Selection Recall: 100.00%
- Tool Selection F1: 100.00%
- Exact Tool Set Accuracy: 100.00%
- Average Tool Calls: 2.5

## Latency

- Mean: 23391.4 ms
- P50: 20424.3 ms
- P95: 43033.2 ms
- Min: 7248.1 ms
- Max: 117501.4 ms

## Retrieval Observation

- Knowledge calls observed: 51
- Successful knowledge calls: 51
- Failed knowledge calls: 0

## Failure Summary

- Primary taxonomy counts: `{'DECISION_ERROR': 8, 'MISSING_INFO_ROUTING_ERROR': 1}`
- Missed escalation cases: `['REF-006', 'REF-007', 'DEL-010', 'PAS-010', 'ACC-006', 'ACC-008', 'OTH-008', 'OTH-009']`

## Known Limitations

This is a controlled 60-case portfolio benchmark against one configured model and knowledge dataset. It is not production traffic, a production SLA, or an industry benchmark. Latency includes external service conditions during this single sequential run. AUTO_RESOLVE is only a routing candidate and does not execute a refund.
