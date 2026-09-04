# Stage 5 Agent Integration Smoke

## Scope

This is a limited real DeepSeek + Stage 4 Tools + RAGFlow integration smoke. It is not a final evaluation benchmark and does not execute refunds.

## Result

- Total cases: 10
- Completed cases: 10
- Expected intent and decision passed: 10/10
- Secrets, full prompts, full RAG chunks, customer/order identifiers, and dataset identifiers are omitted

| Case | Intent | Decision | Tools | Calls | Latency ms | Result |
|---|---|---|---|---:|---:|---:|
| AS-01 | RETURN_REFUND | AUTO_RESOLVE | lookup_customer, lookup_order, search_knowledge, evaluate_refund | 4 | 21505.9 | PASS |
| AS-02 | RETURN_REFUND | NEED_MORE_INFO | search_knowledge | 1 | 34602.2 | PASS |
| AS-03 | RETURN_REFUND | ESCALATE_TO_HUMAN | lookup_customer, lookup_order, search_knowledge, evaluate_refund | 4 | 25210.6 | PASS |
| AS-04 | DELIVERY | AUTO_RESOLVE | lookup_customer, lookup_order, search_knowledge | 3 | 15823.2 | PASS |
| AS-05 | PRODUCT_AFTER_SALES | AUTO_RESOLVE | lookup_customer, lookup_order, search_knowledge | 3 | 13325.4 | PASS |
| AS-06 | ACCOUNT | AUTO_RESOLVE | lookup_customer, search_knowledge | 2 | 14636.5 | PASS |
| AS-07 | INVOICE | AUTO_RESOLVE | lookup_customer, lookup_order, search_knowledge | 3 | 11163.0 | PASS |
| AS-08 | OTHER | AUTO_RESOLVE | none | 0 | 8954.9 | PASS |
| AS-09 | RETURN_REFUND | ESCALATE_TO_HUMAN | lookup_customer, lookup_order, search_knowledge, evaluate_refund | 4 | 16532.3 | PASS |
| AS-10 | DELIVERY | NEED_MORE_INFO | search_knowledge | 1 | 62495.4 | PASS |

## Failures

No failed cases.

## Limitations

This suite checks a small fixed set of requests against one configured model and knowledge dataset. It does not measure production accuracy, safety, latency SLOs, or final benchmark performance.
