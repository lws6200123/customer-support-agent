# Stage 2 Demo Dataset

## Source dataset

The build uses the immutable Olist Brazilian E-Commerce Public Dataset from Kaggle (`olistbr/brazilian-ecommerce`). The raw CSV files are never rewritten. The geolocation table is intentionally excluded because the demo does not require its roughly one million rows.

## Deterministic scenario-aware selection

- Source orders: 99,441
- Selected unique orders: 2,000
- Random seed: `20260903`
- Selected order-set SHA256: `97fc137e58101af532056d9acc11c1477606444f32da68f4e6568af892a8dfd1`
- Created and approved orders are fully retained; configured quotas cover shipped, canceled, unavailable, invoiced, processing, on-time/late delivery, low reviews, multi-item, multi-payment, and source anomalies.

### Scenario distribution

Scenarios overlap, so counts do not sum to the selected order count.

- `approved`: 2
- `canceled`: 104
- `created`: 5
- `delivered_late`: 310
- `delivered_on_time`: 1,194
- `duplicate_source_review_id`: 37
- `invoiced`: 81
- `low_review`: 704
- `multi_item`: 311
- `multi_payment`: 213
- `processing`: 81
- `shipped`: 109
- `shipped_not_overdue`: 63
- `shipped_overdue`: 46
- `source_chronology_anomaly`: 10
- `unavailable`: 104

## Customer identity mapping

Olist `customer_unique_id` is mapped to a stable Demo `CUST-######` identifier. Every order-context `customer_id` is retained as `source_customer_id`; it is not presented as a permanent person identifier. Multiple selected orders with the same `customer_unique_id` map to one Demo customer. Display names are anonymous (`Customer-######`), and no names, email addresses, or phone numbers are generated.

## Simulation clock and timeline normalization

The fixed business clock is `2026-09-03T12:00:00`. Each order receives exactly one deterministic offset. That same offset is applied to purchase, approval, carrier handoff, delivery, estimated delivery, shipping-limit, and review timestamps. Therefore original intervals and relations—including real late deliveries—remain unchanged.

Delivered orders are anchored 1–30 days before the clock; shipped estimates are anchored within ±7 days; active pre-shipment statuses are recent; canceled/unavailable orders are mapped to recent history. Source chronology anomalies remain flagged and are not repaired.

## Processed table row counts

- `customers`: 1,997
- `orders`: 2,000
- `order_items`: 2,314
- `payments`: 2,277
- `reviews`: 1,989
- `products`: 1,709
- `sellers`: 811
- `customer_support_profiles`: 1,997
- `tickets`: 24
- `refunds`: 8

## Referential integrity

- `orders.customer_id -> customers.customer_id`: 0 orphan rows
- `order_items.order_id -> orders.order_id`: 0 orphan rows
- `order_items.product_id -> products.product_id`: 0 orphan rows
- `order_items.seller_id -> sellers.seller_id`: 0 orphan rows
- `payments.order_id -> orders.order_id`: 0 orphan rows
- `reviews.order_id -> orders.order_id`: 0 orphan rows
- `profiles.customer_id -> customers.customer_id`: 0 orphan rows
- `tickets.order_id -> orders.order_id`: 0 orphan rows
- `refunds.order_id -> orders.order_id`: 0 orphan rows

## Source anomalies

- Selected orders with a source chronology flag: 10
- Selected review rows participating in a duplicated source review ID: 6
- These are preserved as lineage/data-quality facts. Normal business-rule examples should filter to `source_data_quality_flag = 'none'`.

## Real, derived, and synthetic boundary

Olist order status, line items, product attributes, seller location, payments, reviews, and customer location are real anonymized source facts. Demo IDs, scenario labels, normalized timestamps, and overdue evaluation are deterministic derivatives.

Membership level, risk flag, account status, identity verification, preferred language, support tickets, and refunds are explicitly labeled `synthetic_operational_data`; Olist does not provide these customer-support operations fields.

### Synthetic profile distribution

- Membership: `{'gold': 185, 'normal': 1405, 'platinum': 51, 'silver': 356}`
- Account status: `{'active': 1908, 'restricted': 40, 'suspended': 49}`
- Preferred language: `{'en': 66, 'es': 16, 'pt-BR': 1915}`
- Risk flagged: 58 / 1,997
- Identity verified: 1,890 / 1,997

## Limitations

The sample is optimized for scenario coverage rather than population-level estimates. Olist lacks internal case notes, policy decisions, shipment tracking events, return logistics, refund approval workflow, customer contacts, inventory state, fraud decisions, and agent activity. Synthetic records exist only to exercise the operational schema and must not be treated as measured Olist behavior.
