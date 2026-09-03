---
document_id: POL-OPS-010
title: DemoShop Customer Support Operations
document_type: operational_policy
source_type: simulated_internal
source_organization: DemoShop
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [ticket, intent, priority, decision, lifecycle, communication]
---

SIMULATED INTERNAL POLICY
For portfolio demonstration only.

## Ticket classification

Use one top-level intent and a permitted sub-intent from `intent_taxonomy.yaml`. Assign priority using the simulated SLA policy. Do not create new production taxonomies from free-form labels during Stage 3.

## Decision states

- `NEED_MORE_INFO`: required facts are absent and no known mandatory escalation condition takes precedence.
- `AUTO_RESOLVE`: a complete routine response or rule-qualified automation candidate can proceed in a future controlled workflow.
- `ESCALATE_TO_HUMAN`: a risk, sensitive action, ambiguity, inconsistency, safety/legal concern, or other canonical escalation rule applies.

The valid decision enum and precedence are defined only in `business_rules.yaml`.

## Information completeness

Request only information relevant to the case: appropriate customer/order identifier, affected item, observed issue, desired outcome, timing, evidence, and any required verification state. Never request passwords, one-time codes, API keys, or payment credentials.

## Lifecycle principles

A conceptual ticket lifecycle is `open → awaiting_customer/under_review → resolved → closed`. Reopen when material new evidence arrives, the issue recurs, or the recorded resolution did not address the request. Do not close solely because an automated message was sent.

Tickets and refunds in the Stage 2 database are synthetic historical examples. Runtime agent tables remain empty and Stage 3 does not create agent activity.

## Communication principles

Separate known facts from estimates and policy conditions. State missing information directly, avoid unsupported guarantees, explain escalation without alleging wrongdoing, and summarize the next action. Public-policy-derived guidance must never be represented as DemoShop's real corporate source material.
