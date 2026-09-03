---
document_id: POL-SHIPPING-003
title: DemoShop Shipping and Delivery Reference Policy
document_type: customer_service_policy
source_type: public_policy_derived
source_organization: JD.com Help Center
source_ids: [JD_DELIVERY_TIMELINESS]
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [shipping, estimated_delivery, delay, exceptions, customer_communication]
---

## Scope and provenance

This document paraphrases a public delivery-timeliness reference for the DemoShop simulation. It does not claim that Olist orders were fulfilled by JD.com or that DemoShop is a real JD.com system.

## Interpreting order times

`estimated_delivery_at` is an estimate, not proof of actual delivery and not by itself a legal or compensation determination. Actual status should be explained using the available order status, carrier handoff, delivered timestamp, and the fixed simulation business clock.

For a shipped order:

- if the estimate is still in the future, explain that the order is in transit and provide the available estimate;
- if the estimate has passed without a delivery record, describe it as overdue for Demo query purposes and recommend a logistics check;
- if source timestamps are contradictory, do not apply normal automated conclusions—escalate the data inconsistency.

## Delay and exceptional circumstances

Transport controls, severe weather or other force-majeure events, holidays, promotions, capacity constraints, destination access, and similar conditions can extend delivery time. The public reference treats displayed timing as a system estimate and actual logistics as controlling.

A delay should not automatically be described as unlawful, automatically compensable, lost, or canceled. Customer-facing handling should acknowledge the estimate, state known facts, avoid unsupported guarantees, and identify the next check or escalation.

## Damage or missing contents

If the parcel arrived damaged or incomplete, capture package condition, affected items, delivery observations, and evidence, then use the product after-sales policy. Do not conflate late delivery with physical damage or missing-item eligibility.
