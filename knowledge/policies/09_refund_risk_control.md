---
document_id: POL-RISK-009
title: DemoShop Refund Risk Control Specification
document_type: operational_policy
source_type: simulated_internal
source_organization: DemoShop
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [refund, risk_control, auto_approval_candidate, human_review]
---

SIMULATED INTERNAL POLICY
For portfolio demonstration only.

## Automation candidate definition

A refund request is an `AUTO_RESOLVE` candidate only when every condition in `business_rules.yaml.refund_rules.auto_approval_candidate_conditions` passes:

- customer-facing return/refund policy eligibility is established;
- amount is at or below the canonical automatic limit;
- no customer risk flag is present;
- the account is active;
- required identity verification is satisfied;
- the count of prior approved refunds is strictly below the canonical threshold within its configured window; the current request is excluded;
- source data relevant to the decision has no quality anomaly;
- no suspected fraud or policy ambiguity is present.

Any failed eligibility/control condition follows the canonical `otherwise_decision`. Missing required facts follow `NEED_MORE_INFO` only if no known escalation rule has already triggered.

## Meaning of AUTO_RESOLVE

`AUTO_RESOLVE` is a classification for a future controlled workflow. This Markdown file does not execute, approve, settle, or promise a refund. Actual money movement is outside Stage 3.

## Evidence and auditability

The future rule engine should record evaluated fields, rule references, decision, and timestamp without storing payment credentials. It must use current structured values and must not infer risk, identity, or policy eligibility from conversational tone.

All limits and frequency values live only in `business_rules.yaml.simulation_business`. Currency and prior-refund counting semantics live in the adjacent canonical semantic blocks; this document must not become a second source of truth.
