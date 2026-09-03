---
document_id: POL-ACCOUNT-006
title: DemoShop Account Security Reference Policy
document_type: customer_service_policy
source_type: public_policy_derived
source_organization: JD.com Help Center
source_ids: [JD_ACCOUNT_RISK, JD_ACCOUNT_LOCK]
version: 1.0.0
status: active
effective_date: 2026-09-03
language: en
topics: [account_risk, password_reset, verification, lock, unlock, escalation]
---

## Scope and provenance

This document paraphrases public account-security guidance for DemoShop knowledge preparation. DemoShop does not implement a real authentication system in Stage 3, and this policy does not expose or reuse JD.com account controls.

## Abnormal or at-risk account

When a customer reports abnormal access, account risk, or suspected compromise, prioritize containment and verified support channels. Recommend password reset through the approved account interface, review of available security settings, and avoidance of sharing passwords, verification codes, or secret credentials with support.

Do not ask the customer to transmit sensitive authentication secrets. Do not claim the account is safe solely because an order record is available.

## Lock and unlock guidance

Locking can be used as a protective step when unauthorized access is suspected. Unlocking or other sensitive restoration should require identity verification and may require a password reset. Explain the expected effect of a lock and direct the customer to the supported account-security flow.

## Escalation boundary

An account that is restricted, suspended, locked, at risk, or not adequately verified must follow the canonical `account_rules` and `escalation_rules` in `business_rules.yaml`. Customer-service knowledge can describe next steps but cannot authenticate, lock, unlock, or recover an account by itself.
