# Stage 1 — Olist Real E-Commerce Data Audit

## 1. Dataset Source

- Dataset: Olist Brazilian E-Commerce Public Dataset
- Kaggle slug: `olistbr/brazilian-ecommerce`
- Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- License: needs confirmation from a trustworthy source before reuse or redistribution.
- Audit generated at: `2026-09-03T03:47:20.886484+00:00`
- Raw CSV files were read without modification.

## 2. Raw Files

| Filename | Size (bytes) | SHA256 |
|---|---:|---|
| `olist_customers_dataset.csv` | 9,033,957 | `983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2` |
| `olist_geolocation_dataset.csv` | 61,273,883 | `b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6` |
| `olist_order_items_dataset.csv` | 15,438,671 | `0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279` |
| `olist_order_payments_dataset.csv` | 5,777,138 | `4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0` |
| `olist_order_reviews_dataset.csv` | 14,451,670 | `012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7` |
| `olist_orders_dataset.csv` | 17,654,914 | `8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf` |
| `olist_products_dataset.csv` | 2,379,446 | `3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc` |
| `olist_sellers_dataset.csv` | 174,703 | `1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e` |
| `product_category_name_translation.csv` | 2,613 | `a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278` |

Expected filenames not found: none

Additional CSV files found: none

## 3. Table Overview

| Table | File | Rows | Columns | Exact duplicate rows |
|---|---|---:|---:|---:|
| `customers` | `olist_customers_dataset.csv` | 99,441 | 5 | 0 |
| `geolocation` | `olist_geolocation_dataset.csv` | 1,000,163 | 5 | 261,831 |
| `order_items` | `olist_order_items_dataset.csv` | 112,650 | 7 | 0 |
| `payments` | `olist_order_payments_dataset.csv` | 103,886 | 5 | 0 |
| `reviews` | `olist_order_reviews_dataset.csv` | 99,224 | 7 | 0 |
| `orders` | `olist_orders_dataset.csv` | 99,441 | 8 | 0 |
| `products` | `olist_products_dataset.csv` | 32,951 | 9 | 0 |
| `sellers` | `olist_sellers_dataset.csv` | 3,095 | 4 | 0 |
| `category_translation` | `product_category_name_translation.csv` | 71 | 2 | 0 |

## 4. Key Schema

### customers

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `customer_id` | `object` | 0 | 0.0000% | 99,441 | unique among non-null values |
| `customer_unique_id` | `object` | 0 | 0.0000% | 96,096 | not unique (6,342 affected rows) |
| `customer_zip_code_prefix` | `int64` | 0 | 0.0000% | 14,994 | — |
| `customer_city` | `object` | 0 | 0.0000% | 4,119 | — |
| `customer_state` | `object` | 0 | 0.0000% | 27 | — |

### geolocation

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `geolocation_zip_code_prefix` | `int64` | 0 | 0.0000% | 19,015 | — |
| `geolocation_lat` | `float64` | 0 | 0.0000% | 717,360 | — |
| `geolocation_lng` | `float64` | 0 | 0.0000% | 717,613 | — |
| `geolocation_city` | `object` | 0 | 0.0000% | 8,011 | — |
| `geolocation_state` | `object` | 0 | 0.0000% | 27 | — |

### order_items

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `order_id` | `object` | 0 | 0.0000% | 98,666 | not unique (23,787 affected rows) |
| `order_item_id` | `int64` | 0 | 0.0000% | 21 | not unique (112,649 affected rows) |
| `product_id` | `object` | 0 | 0.0000% | 32,951 | not unique (94,533 affected rows) |
| `seller_id` | `object` | 0 | 0.0000% | 3,095 | not unique (112,141 affected rows) |
| `shipping_limit_date` | `object` | 0 | 0.0000% | 93,318 | — |
| `price` | `float64` | 0 | 0.0000% | 5,968 | — |
| `freight_value` | `float64` | 0 | 0.0000% | 6,999 | — |

### payments

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `order_id` | `object` | 0 | 0.0000% | 99,440 | not unique (7,407 affected rows) |
| `payment_sequential` | `int64` | 0 | 0.0000% | 29 | — |
| `payment_type` | `object` | 0 | 0.0000% | 5 | — |
| `payment_installments` | `int64` | 0 | 0.0000% | 24 | — |
| `payment_value` | `float64` | 0 | 0.0000% | 29,077 | — |

### reviews

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `review_id` | `object` | 0 | 0.0000% | 98,410 | not unique (1,603 affected rows) |
| `order_id` | `object` | 0 | 0.0000% | 98,673 | not unique (1,098 affected rows) |
| `review_score` | `int64` | 0 | 0.0000% | 5 | — |
| `review_comment_title` | `object` | 87,656 | 88.3415% | 4,527 | — |
| `review_comment_message` | `object` | 58,247 | 58.7025% | 36,159 | — |
| `review_creation_date` | `object` | 0 | 0.0000% | 636 | — |
| `review_answer_timestamp` | `object` | 0 | 0.0000% | 98,248 | — |

### orders

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `order_id` | `object` | 0 | 0.0000% | 99,441 | unique among non-null values |
| `customer_id` | `object` | 0 | 0.0000% | 99,441 | unique among non-null values |
| `order_status` | `object` | 0 | 0.0000% | 8 | — |
| `order_purchase_timestamp` | `object` | 0 | 0.0000% | 98,875 | — |
| `order_approved_at` | `object` | 160 | 0.1609% | 90,733 | — |
| `order_delivered_carrier_date` | `object` | 1,783 | 1.7930% | 81,018 | — |
| `order_delivered_customer_date` | `object` | 2,965 | 2.9817% | 95,664 | — |
| `order_estimated_delivery_date` | `object` | 0 | 0.0000% | 459 | — |

### products

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `product_id` | `object` | 0 | 0.0000% | 32,951 | unique among non-null values |
| `product_category_name` | `object` | 610 | 1.8512% | 73 | — |
| `product_name_lenght` | `float64` | 610 | 1.8512% | 66 | — |
| `product_description_lenght` | `float64` | 610 | 1.8512% | 2,960 | — |
| `product_photos_qty` | `float64` | 610 | 1.8512% | 19 | — |
| `product_weight_g` | `float64` | 2 | 0.0061% | 2,204 | — |
| `product_length_cm` | `float64` | 2 | 0.0061% | 99 | — |
| `product_height_cm` | `float64` | 2 | 0.0061% | 102 | — |
| `product_width_cm` | `float64` | 2 | 0.0061% | 95 | — |

### sellers

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `seller_id` | `object` | 0 | 0.0000% | 3,095 | unique among non-null values |
| `seller_zip_code_prefix` | `int64` | 0 | 0.0000% | 2,246 | — |
| `seller_city` | `object` | 0 | 0.0000% | 611 | — |
| `seller_state` | `object` | 0 | 0.0000% | 23 | — |

### category_translation

| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |
|---|---|---:|---:|---:|---|
| `product_category_name` | `object` | 0 | 0.0000% | 71 | — |
| `product_category_name_english` | `object` | 0 | 0.0000% | 71 | — |

## 5. Data Quality

- Tables with exact duplicate rows: `geolocation` (261,831)
- Non-unique suspected ID columns: `customers.customer_unique_id` (6,342 affected rows), `order_items.order_id` (23,787 affected rows), `order_items.order_item_id` (112,649 affected rows), `order_items.product_id` (94,533 affected rows), `order_items.seller_id` (112,141 affected rows), `payments.order_id` (7,407 affected rows), `reviews.review_id` (1,603 affected rows), `reviews.order_id` (1,098 affected rows)
- Candidate composite-key checks: `order_items(order_id, order_item_id)`: unique; `payments(order_id, payment_sequential)`: unique
- Numeric sign scan: `geolocation.geolocation_lat` (998,827), `geolocation.geolocation_lng` (1,000,160). Negative latitude/longitude values are geographically expected for Brazil and are not, by themselves, data-quality failures.
- Nulls must be interpreted by business state; for example, delivery timestamps can be legitimately absent for cancelled or unavailable orders.
- Orders without a corresponding child record: `order_items` 775, `payments` 1, `reviews` 768.
- Product categories without an English translation row: `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`.
- Payment rows with `payment_type=not_defined`: 3.

## 6. Order Status Distribution

| Status | Count | Share |
|---|---:|---:|
| `delivered` | 96,478 | 97.0203% |
| `shipped` | 1,107 | 1.1132% |
| `canceled` | 625 | 0.6285% |
| `unavailable` | 609 | 0.6124% |
| `invoiced` | 314 | 0.3158% |
| `processing` | 301 | 0.3027% |
| `created` | 5 | 0.0050% |
| `approved` | 2 | 0.0020% |

## 7. Timestamp Range

| Field | Min | Max | Nulls | Invalid non-null values |
|---|---|---|---:|---:|
| `order_purchase_timestamp` | `2016-09-04 21:15:19` | `2018-10-17 17:30:18` | 0 | 0 |
| `order_approved_at` | `2016-09-15 12:16:38` | `2018-09-03 17:40:06` | 160 | 0 |
| `order_delivered_carrier_date` | `2016-10-08 10:34:01` | `2018-09-11 19:48:28` | 1,783 | 0 |
| `order_delivered_customer_date` | `2016-10-11 13:46:32` | `2018-10-17 13:22:46` | 2,965 | 0 |
| `order_estimated_delivery_date` | `2016-09-30 00:00:00` | `2018-11-12 00:00:00` | 0 | 0 |

Timestamp nulls by order status:

- `order_purchase_timestamp`: none
- `order_approved_at`: `canceled` 141, `delivered` 14, `created` 5
- `order_delivered_carrier_date`: `unavailable` 609, `canceled` 550, `invoiced` 314, `processing` 301, `created` 5, `approved` 2, `delivered` 2
- `order_delivered_customer_date`: `shipped` 1,107, `canceled` 619, `unavailable` 609, `invoiced` 314, `processing` 301, `delivered` 8, `created` 5, `approved` 2
- `order_estimated_delivery_date`: none

Observed timestamp relationships:

| Check | Count | Comparable rows | Rate | Interpretation |
|---|---:|---:|---:|---|
| `approval_before_purchase` | 0 | 99,281 | 0.0000% | chronology anomaly |
| `carrier_handoff_before_purchase` | 166 | 97,658 | 0.1700% | chronology anomaly |
| `customer_delivery_before_purchase` | 0 | 96,476 | 0.0000% | chronology anomaly |
| `carrier_handoff_before_approval` | 1,359 | 97,644 | 1.3918% | chronology anomaly |
| `customer_delivery_before_carrier_handoff` | 23 | 96,475 | 0.0238% | chronology anomaly |
| `estimated_delivery_before_purchase` | 0 | 99,441 | 0.0000% | chronology anomaly |
| `delivered_after_estimate` | 7,827 | 96,476 | 8.1129% | service outcome, not necessarily invalid |

Chronology exceptions indicate source-record ordering inconsistencies or differing operational timestamp semantics; they must not be silently corrected. `delivered_after_estimate` is a customer-service lateness signal rather than a chronology error.

## 8. Table Relationships

| Relationship | Parent key unique | Child rows | Unmatched rows | Unmatched distinct keys | Match rate | Observed cardinality |
|---|---|---:|---:|---:|---:|---|
| `orders.customer_id -> customers.customer_id` | True | 99,441 | 0 | 0 | 100.000000% | 1:1 |
| `order_items.order_id -> orders.order_id` | True | 112,650 | 0 | 0 | 100.000000% | 1:N |
| `order_items.product_id -> products.product_id` | True | 112,650 | 0 | 0 | 100.000000% | 1:N |
| `order_items.seller_id -> sellers.seller_id` | True | 112,650 | 0 | 0 | 100.000000% | 1:N |
| `payments.order_id -> orders.order_id` | True | 103,886 | 0 | 0 | 100.000000% | 1:N |
| `reviews.order_id -> orders.order_id` | True | 99,224 | 0 | 0 | 100.000000% | 1:N |

## 9. Fields Useful for Customer Support Agent

- **CustomerTool:** `customers.customer_id`, `customers.customer_unique_id`, `customers.customer_zip_code_prefix`, `customers.customer_city`, `customers.customer_state` — customer/order lookup and coarse delivery region.
- **OrderTool:** `orders.order_id`, `orders.customer_id`, `orders.order_status`, `orders.order_purchase_timestamp`, `orders.order_approved_at`, `orders.order_delivered_carrier_date`, `orders.order_delivered_customer_date`, `orders.order_estimated_delivery_date`, `order_items.order_id`, `order_items.order_item_id`, `order_items.product_id`, `order_items.seller_id`, `order_items.shipping_limit_date`, `order_items.price`, `order_items.freight_value` — order state, item composition, seller, value, and delivery milestones.
- **RefundTool analysis:** `payments.order_id`, `payments.payment_sequential`, `payments.payment_type`, `payments.payment_installments`, `payments.payment_value` — original payment context only; no refund workflow is present.
- **Shipping / Delivery:** `orders.order_purchase_timestamp`, `orders.order_approved_at`, `orders.order_delivered_carrier_date`, `orders.order_delivered_customer_date`, `orders.order_estimated_delivery_date`, `order_items.shipping_limit_date`, `order_items.freight_value`, `order_items.seller_id`, `customers.customer_zip_code_prefix`, `customers.customer_city`, `customers.customer_state`, `sellers.seller_zip_code_prefix`, `sellers.seller_city`, `sellers.seller_state` — delivery progress, lateness, origin/destination region, and freight context.
- **Product after-sales:** `products.product_id`, `products.product_category_name`, `products.product_weight_g`, `products.product_length_cm`, `products.product_height_cm`, `products.product_width_cm`, `reviews.order_id`, `reviews.review_score`, `reviews.review_comment_title`, `reviews.review_comment_message`, `category_translation.product_category_name`, `category_translation.product_category_name_english` — category, physical attributes, and post-order review signals.

## 10. Missing Business Fields

The public Olist transaction files do not provide a complete customer-service operations model. A later, explicitly synthetic overlay will be needed for:

- Support ticket ID, channel, queue, priority, reason, lifecycle, SLA, assignee, and resolution.
- Customer name, email, phone number, identity-verification result, and consent/contact preferences.
- Refund request, eligibility decision, approval chain, refund amount, refund status, and settlement timestamp.
- Risk/fraud flags, manual-review outcomes, account notes, and internal escalation history.
- Shipment tracking events, carrier support case IDs, proof of delivery, return merchandise authorization, and return receipt.
- Product warranty rules, defect classification, replacement workflow, inventory availability, and policy exceptions.

## 11. Risks / Limitations

- The dataset is a historical marketplace snapshot, not a live operational support system.
- `customer_id` is order-context identity; `customer_unique_id` is the better cross-order customer identifier, but neither provides contact identity.
- Reviews are post-order feedback, not customer-support tickets or verified issue labels.
- Payment rows can be one-to-many per order; aggregations must preserve payment grain.
- Order items can be one-to-many per order and seller/product combinations can repeat; joins can multiply rows.
- Geolocation is large and contains repeated ZIP-prefix coordinates; full ingestion is unnecessary for a compact demo.
- Timestamps have no explicit timezone metadata in the CSV fields; do not infer timezone-dependent SLA behavior without documentation.
- License terms require confirmation from a trustworthy source before redistribution decisions.

## 12. Recommendations for Stage 2

- Treat the manifest hashes as the immutable raw-data baseline.
- Define the Stage 2 demo population only after preserving entity and relationship coverage across orders, items, payments, reviews, products, sellers, and customers.
- Keep operational support fields in a clearly labeled synthetic overlay rather than modifying Olist raw records.
- Preserve source keys in downstream tables so every demo record remains traceable to Olist or to the synthetic overlay.
- Consider excluding full geolocation detail from the demo database; retain only fields needed for delivery reasoning or derived regional context.
