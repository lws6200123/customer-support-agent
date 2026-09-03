---
document_id: POL-SLA-007
title: DemoShop Customer Service SLA
document_type: operational_policy
source_type: simulated_internal
source_organization: DemoShop
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [sla, priority, response_target, queue_management]
---

SIMULATED INTERNAL POLICY
For portfolio demonstration only.

## Purpose

This policy defines DemoShop's simulated initial-response targets. It is not sourced from JD.com or Olist and must not be presented as a real company's SLA.

## Priority model

- `LOW`: general questions with no material time sensitivity.
- `NORMAL`: routine order, return, refund-status, or invoice questions.
- `HIGH`: significant delivery/after-sales impact, a blocked customer action, or a time-sensitive unresolved issue.
- `URGENT`: safety-sensitive, credible account-compromise, legal/regulatory, or similarly critical handling.

The only canonical response-time values are `business_rules.yaml.sla.*.response_minutes`. This document deliberately does not duplicate the numbers.

## Measurement

The clock measures time from ticket creation to the first meaningful response. Automated acknowledgement alone is not a meaningful response. A response target is not a promise of final resolution.

When priority changes, record the reason and apply the new target prospectively under the future workflow design. Queue age, repeated contacts, and customer impact may justify raising priority but must not silently lower it.

## Exceptions and escalation

An SLA breach does not change refund eligibility or create automatic compensation. Urgent, ambiguous, unsafe, or blocked cases follow the manual escalation policy. Stage 3 defines knowledge only and does not run an SLA scheduler.
