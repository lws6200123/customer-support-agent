---
document_id: POL-REFUND-004
title: DemoShop Refund Processing Reference Policy
document_type: customer_service_policy
source_type: public_policy_derived
source_organization: JD.com Help Center
source_ids: [JD_REFUND_EXPLANATION]
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [refund, payment_route, processing_status, bank_processing]
---

## Scope and provenance

This is a paraphrased public-policy reference used by the DemoShop portfolio simulation. It does not reproduce a real DemoShop refund promise, and its public source is separate from Olist transaction data.

## Initiation and routing

A refund-status explanation should distinguish approval/initiation from actual receipt. Confirm the order, refund record, amount, original payment components, current refund status, initiation time, and whether an external payment provider is involved.

The public reference generally routes eligible refunds back through the original payment path, but combined payment methods, stored-value instruments, corporate transfer, installment products, or provider-specific constraints may produce different handling. Do not promise a destination that is unsupported by recorded payment facts.

## Processing stages

Explain separately:

1. the platform-side review or initiation stage;
2. handoff to the original payment channel;
3. external bank/payment-provider processing;
4. final settlement or a failed/exception status.

Different payment methods and financial institutions may have different processing periods. This knowledge base intentionally does not collapse them into one universal arrival time. Published timing is an estimate and external processing can vary.

## Operational boundary

This document helps explain facts; it does not issue money. DemoShop automatic-refund candidacy and mandatory escalation use the canonical thresholds and conditions in `business_rules.yaml`. Missing payment data, contradictory totals, ambiguous policy, or an unexpected destination requires more information or human review.
