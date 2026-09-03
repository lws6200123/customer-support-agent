# Stage 4 Knowledge Retrieval Smoke

## Scope

This is a real RAGFlow retrieval-only integration smoke test. It does not call an LLM and is not a final evaluation benchmark.

## Configuration

- Retrieval mode: hybrid baseline without reranker
- Top N: 5
- Similarity threshold: 0.2
- Vector similarity weight: 0.7
- API key and dataset identifier: configured locally and intentionally omitted
- Exposed `score`: RAGFlow overall retrieval score; it is not labelled as vector cosine similarity

## Results

- Cases: 15
- Top-1 expected hit: 13/15 (86.7%)
- Top-3 expected hit: 15/15 (100.0%)

| Case | Expected | Retrieved (ranked) | Scores | Top-1 | Top-3 |
|---|---|---|---|---:|---:|
| KS-01 | POL-RETURN-001 | POL-RETURN-001, POL-RETURN-001, POL-AFTERSALES-002, POL-RISK-009, POL-REFUND-004 | 0.6245, 0.5612, 0.5466, 0.5194, 0.5179 | pass | pass |
| KS-02 | POL-AFTERSALES-002 | POL-AFTERSALES-002, POL-RETURN-001, POL-SHIPPING-003, POL-RETURN-001, POL-REFUND-004 | 0.5951, 0.5692, 0.5276, 0.5016, 0.4779 | pass | pass |
| KS-03 | POL-AFTERSALES-002 | POL-AFTERSALES-002, POL-SHIPPING-003, POL-RETURN-001, POL-RETURN-001, POL-SLA-007 | 0.6457, 0.6306, 0.5904, 0.5563, 0.5401 | pass | pass |
| KS-04 | POL-SHIPPING-003 | POL-SHIPPING-003, POL-SLA-007, POL-REFUND-004, POL-RETURN-001, POL-AFTERSALES-002 | 0.642, 0.5178, 0.5124, 0.5061, 0.5054 | pass | pass |
| KS-05 | POL-REFUND-004 | POL-REFUND-004, POL-RISK-009, POL-RETURN-001, POL-INVOICE-005, POL-ESCALATION-008 | 0.6267, 0.5671, 0.5603, 0.5417, 0.5132 | pass | pass |
| KS-06 | POL-INVOICE-005 | POL-INVOICE-005, POL-OPS-010, POL-RETURN-001, POL-RISK-009, POL-REFUND-004 | 0.6141, 0.4886, 0.4725, 0.4707, 0.4614 | pass | pass |
| KS-07 | POL-ACCOUNT-006 | POL-ACCOUNT-006, POL-RETURN-001, POL-RISK-009, POL-OPS-010, POL-ESCALATION-008 | 0.6038, 0.523, 0.508, 0.5059, 0.5044 | pass | pass |
| KS-08 | POL-SLA-007 | POL-SLA-007, POL-OPS-010, POL-ESCALATION-008, POL-RETURN-001, POL-REFUND-004 | 0.6649, 0.5817, 0.5318, 0.5183, 0.5001 | pass | pass |
| KS-09 | POL-ESCALATION-008 | POL-ESCALATION-008, POL-RISK-009, POL-RETURN-001, POL-REFUND-004, POL-OPS-010 | 0.6483, 0.6203, 0.5917, 0.5835, 0.561 | pass | pass |
| KS-10 | POL-RISK-009 | POL-RISK-009, POL-REFUND-004, POL-RETURN-001, POL-ESCALATION-008, POL-OPS-010 | 0.6089, 0.5792, 0.5598, 0.5454, 0.5192 | pass | pass |
| KS-11 | POL-OPS-010 | POL-OPS-010, POL-RETURN-001, POL-INVOICE-005, POL-REFUND-004, POL-RISK-009 | 0.5763, 0.5186, 0.4977, 0.4943, 0.4929 | pass | pass |
| KS-12 | POL-RETURN-001 | POL-RETURN-001, POL-AFTERSALES-002, POL-SHIPPING-003, POL-RETURN-001, POL-INVOICE-005 | 0.5629, 0.5566, 0.5157, 0.5075, 0.4896 | pass | pass |
| KS-13 | POL-AFTERSALES-002 | POL-SHIPPING-003, POL-RETURN-001, POL-AFTERSALES-002, POL-INVOICE-005, POL-RETURN-001 | 0.5493, 0.5485, 0.5411, 0.5304, 0.4945 | fail | pass |
| KS-14 | POL-REFUND-004 | POL-REFUND-004, POL-RETURN-001, POL-RISK-009, POL-SHIPPING-003, POL-INVOICE-005 | 0.6163, 0.5258, 0.5236, 0.5124, 0.5103 | pass | pass |
| KS-15 | POL-ESCALATION-008 | POL-RETURN-001, POL-ESCALATION-008, POL-RISK-009, POL-OPS-010, POL-AFTERSALES-002 | 0.5413, 0.5377, 0.5137, 0.5059, 0.4986 | fail | pass |

## Top-3 Failures

No Top-3 failures.

## Interpretation

These figures validate only the current small policy corpus and fixed smoke questions. They must not be presented as Agent accuracy, production retrieval quality, or a final benchmark.
