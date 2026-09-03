# Stage 2 SQLite Smoke Test

All checks use read-only service/query functions against the generated SQLite database. Identifiers below are anonymized Demo/source identifiers; no contact information is stored.

## Results

1. **Customer profile:** `CUST-000001` returned location, membership `gold`, risk flag `False`, account status `active`, and identity verification `True`.
2. **Order details:** `ORD-000004` returned all 4 items with product/seller attributes, plus payments and reviews.
3. **Late delivery:** `ORD-000017` has delivered time `2026-08-16T07:00:00` after estimate `2026-08-14T08:54:29`.
4. **Shipping clock:** `ORD-000075` evaluated overdue and `ORD-000021` evaluated not overdue at fixed clock `2026-09-03T12:00:00`.
5. **Multi-item:** `ORD-000004` returned 4 complete rows.
6. **Multi-payment:** `ORD-000010` returned 2 payments totaling 30.51.
7. **Duplicate source review ID:** source ID `0a6ec47c5d78509672e16b95efcff53b` is present on 2 rows backed by the same number of unique internal primary keys.

## Database safeguards

- `PRAGMA foreign_keys`: 1 (enabled)
- Empty runtime tables: `{'agent_runs': 0, 'agent_steps': 0, 'feedback': 0}`
- The initialization script builds and validates a temporary database before atomically replacing only `data/seed/customer_support_demo.db`.
