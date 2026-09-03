---
document_id: POL-RETURN-001
title: DemoShop Return and Exchange Reference Policy
document_type: customer_service_policy
source_type: public_policy_derived
source_organization: JD.com Help Center
source_ids: [JD_AFTERSALES_GENERAL, JD_NO_REASON_RETURN]
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [return, exchange, eligibility, product_condition, evidence, exceptions]
---

## Scope and provenance

This document is a paraphrased portfolio reference. It adapts concepts from public help-center material for DemoShop; it is not a statement of JD.com policy for a real DemoShop transaction and is not derived from Olist transactions.

## Eligibility assessment

A return or exchange assessment should establish the order, product, delivery date, requested remedy, reason, product-page eligibility, category-specific conditions, and available evidence. Eligibility cannot be inferred from elapsed time alone.

For a no-reason return, the item must be marked as eligible and remain in a condition consistent with reasonable inspection. The product, accessories, labels, documentation, and other supplied components should be complete. Use beyond what is necessary to inspect function or quality may make the item ineligible.

The canonical reference windows are stored only in:

- `business_rules.yaml.public_reference_parameters.no_reason_return_window_days`
- `business_rules.yaml.public_reference_parameters.quality_return_window_days`
- `business_rules.yaml.public_reference_parameters.quality_exchange_window_days`

## Quality, damage, and inconsistency

A confirmed functional or quality defect may support repair, return, or exchange according to product category and applicable service terms. Delivery damage, missing original components, or a product inconsistent with its description should be recorded promptly and verified before a remedy is selected.

Evidence may include photos, package condition, delivery observations, serial/product identifiers, an authorized inspection result, or other facts reasonably needed to validate the claim. Lack of local inspection capability is a customer-service case, not an automatic denial.

## Exclusions and exceptions

No-reason return treatment may be unavailable for customized, perishable, opened digital/media/software, activated, hygiene/safety-sensitive, near-expiry, disclosed-defect, or other products whose nature or product page excludes such returns. Category-specific rules and the product detail page take precedence over a general assumption.

Unauthorized repair, misuse, accidental damage, altered identifiers, incomplete required components, expired warranty coverage, or inability to return the item in qualifying condition may prevent the requested path. These facts require evidence and should not be presumed.

## Decision boundary

This document describes customer-facing policy considerations. It does not authorize a refund. DemoShop automation candidacy, identity, risk, amount, frequency, ambiguity, and escalation are governed by `business_rules.yaml` and the simulated internal policies.
