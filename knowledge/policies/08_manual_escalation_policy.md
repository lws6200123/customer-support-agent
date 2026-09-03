---
document_id: POL-ESCALATION-008
title: DemoShop Manual Escalation Policy
document_type: operational_policy
source_type: simulated_internal
source_organization: DemoShop
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [manual_review, escalation, risk, safety, policy_ambiguity]
---

SIMULATED INTERNAL POLICY
For portfolio demonstration only.

## Mandatory human review

Use `ESCALATE_TO_HUMAN` when any canonical escalation rule in `business_rules.yaml.escalation_rules` is satisfied. This includes:

- refund amount above `simulation_business.auto_refund_limit`;
- `risk_flag` set;
- account status other than active;
- failed identity verification for a sensitive action;
- suspected fraud or a repeated-refund pattern at the configured frequency threshold;
- ambiguous or conflicting policy applicability;
- a legal or regulatory complaint;
- a threatening or safety-sensitive message;
- inconsistent tool/data results;
- a relevant source-data-quality anomaly.

The refund limit is denominated in the same BRL semantic as the unconverted Olist transaction amounts. It is a DemoShop simulation threshold—not a JD.com, Olist, legal, or industry standard. Its value exists only in `business_rules.yaml`.

## Escalation record

The future workflow should pass the known customer/order/ticket identifiers, triggering rule IDs, relevant evidence, missing facts, and a concise customer-safe summary. It must not copy secrets or unnecessary personal data.

Escalation does not imply approval, denial, wrongdoing, or fraud. A human reviewer owns the final sensitive decision.

## Precedence

Mandatory escalation has precedence over routine resolution. Missing ordinary information yields `NEED_MORE_INFO` only when no mandatory escalation fact is already known. Tool or policy uncertainty must never be hidden by a confident automated answer.
