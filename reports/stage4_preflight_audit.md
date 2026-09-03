# Stage 4 Preflight Audit

## Currency consistency

**Result: PASS**

The Stage 2 pipeline copied Olist `price`, `freight_value`, and `payment_value` without currency conversion. Olist's official dataset description identifies the records as real Brazilian retail transactions. A lineage cross-check inside the same official dataset found an anonymized review that described an item as `R$ 90`; its linked structured order item has `price = 90.0`. The linked item prices plus freight also reconcile to the payment value within source rounding.

Canonical DemoShop simulation currency is therefore `BRL`. `auto_refund_limit` remains a simulated internal DemoShop threshold, but it now has the same unit as transaction and refund amounts. No exchange rate, live FX API, or CNY conversion is used.

Sources reviewed:

- Olist Kaggle dataset metadata: `https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`
- Olist official data challenge repository: `https://github.com/olist/work-at-olist-data`
- Immutable local Stage 1/2 Olist lineage and linked raw tables

## Refund-frequency semantics

**Result: PASS**

`prior_approved_refunds_in_window` means refunds for the same Demo customer with status `approved` and `requested_at` in the half-open interval:

`simulation_now - refund_frequency_window_days <= requested_at < simulation_now`

The current request is not counted. Automatic candidacy requires the prior count to be strictly less than `max_auto_refunds_in_window`. At the configured boundary, a prior count equal to or greater than the maximum triggers `ESCALATE_TO_HUMAN`.

The window size, maximum count, field name, included statuses, boundary inclusivity, current-request treatment, and comparison operator are defined in `knowledge/business_rules.yaml`. `RefundDecisionService` loads these canonical values rather than restating the numeric thresholds in Python.

## RAGFlow API verification

The installed read-only RAGFlow source reports version `0.27.1`. Its SDK and REST implementation confirm:

- endpoint: `POST /api/v1/retrieval`
- authentication: `Authorization: Bearer <key>`
- request fields include `question`, `dataset_ids`, `page`, `page_size`, `similarity_threshold`, `vector_similarity_weight`, `knn_top_k`, `knn_num_candidates`, and optional `rerank_id`
- successful response envelope: `code = 0`, with chunks under `data.chunks`
- chunk mappings include content, document/chunk IDs, document name/keyword, and an overall `similarity` value

The Stage 4 client exposes the overall retrieval value only as `score`; it does not label it as vector cosine similarity or reranker score.
