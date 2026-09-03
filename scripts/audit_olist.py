#!/usr/bin/env python3
"""Audit immutable Olist CSV files and generate reproducible Stage 1 reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


DATASET_SLUG = "olistbr/brazilian-ecommerce"
DATASET_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"

EXPECTED_FILES = (
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)

TABLE_NAMES = {
    "olist_customers_dataset": "customers",
    "olist_geolocation_dataset": "geolocation",
    "olist_order_items_dataset": "order_items",
    "olist_order_payments_dataset": "payments",
    "olist_order_reviews_dataset": "reviews",
    "olist_orders_dataset": "orders",
    "olist_products_dataset": "products",
    "olist_sellers_dataset": "sellers",
    "product_category_name_translation": "category_translation",
}

ORDER_TIMESTAMPS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)

RELATIONSHIPS = (
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("payments", "order_id", "orders", "order_id"),
    ("reviews", "order_id", "orders", "order_id"),
)

COMPOSITE_KEYS = {
    "order_items": ("order_id", "order_item_id"),
    "payments": ("order_id", "payment_sequential"),
}


class AuditError(RuntimeError):
    """Raised when source files cannot support a trustworthy audit."""


def discover_csv_files(raw_dir: Path) -> list[Path]:
    """Return top-level CSV files in deterministic filename order."""
    if not raw_dir.is_dir():
        return []
    return sorted(
        (
            path
            for path in raw_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".csv"
        ),
        key=lambda path: path.name.lower(),
    )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a file SHA256 without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_name_for(path: Path) -> str:
    """Map known Olist filenames to concise logical table names."""
    return TABLE_NAMES.get(path.stem, path.stem)


def build_manifest(files: Iterable[Path]) -> dict[str, Any]:
    """Build immutable-source provenance metadata for raw CSV files."""
    file_entries = [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    return {
        "dataset": "Olist Brazilian E-Commerce Public Dataset",
        "source_slug": DATASET_SLUG,
        "source_url": DATASET_URL,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(file_entries),
        "files": file_entries,
    }


def schema_statistics(frame: pd.DataFrame) -> dict[str, Any]:
    """Compute table- and column-level schema quality statistics."""
    row_count = int(len(frame))
    columns: list[dict[str, Any]] = []
    for column_name in frame.columns:
        series = frame[column_name]
        null_count = int(series.isna().sum())
        non_null = series.dropna()
        suspected_id = column_name == "id" or column_name.endswith("_id")
        column_stats: dict[str, Any] = {
            "name": str(column_name),
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_percentage": (null_count / row_count * 100) if row_count else 0.0,
            "unique_count": int(series.nunique(dropna=True)),
            "suspected_id": suspected_id,
        }
        if suspected_id:
            column_stats["non_null_unique"] = bool(non_null.is_unique)
            column_stats["duplicate_non_null_rows"] = int(
                non_null.duplicated(keep=False).sum()
            )
        columns.append(column_stats)

    numeric_summary: list[dict[str, Any]] = []
    for column_name in frame.select_dtypes(include="number").columns:
        series = frame[column_name]
        non_null = series.dropna()
        numeric_summary.append(
            {
                "name": str(column_name),
                "min": _json_scalar(non_null.min()) if not non_null.empty else None,
                "max": _json_scalar(non_null.max()) if not non_null.empty else None,
                "negative_count": int((non_null < 0).sum()),
            }
        )

    return {
        "row_count": row_count,
        "column_count": int(len(frame.columns)),
        "column_names": [str(column) for column in frame.columns],
        "duplicate_row_count": int(frame.duplicated().sum()),
        "columns": columns,
        "numeric_summary": numeric_summary,
    }


def _json_scalar(value: Any) -> Any:
    """Convert pandas/numpy scalars into JSON-compatible Python values."""
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def read_csv(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    """Read an Olist CSV without mutating it."""
    try:
        return pd.read_csv(path, usecols=usecols, low_memory=False)
    except Exception as exc:  # pandas raises several parser/type exceptions
        raise AuditError(f"Unable to read {path.name}: {exc}") from exc


def audit_tables(files: list[Path]) -> tuple[dict[str, Any], dict[str, Path]]:
    """Profile each discovered CSV and return audits plus logical file mapping."""
    audits: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    for path in files:
        table_name = table_name_for(path)
        if table_name in paths:
            raise AuditError(f"Multiple files resolve to table name {table_name!r}")
        frame = read_csv(path)
        audit = schema_statistics(frame)
        composite_key = COMPOSITE_KEYS.get(table_name)
        if composite_key and all(column in frame.columns for column in composite_key):
            duplicate_count = int(frame.duplicated(list(composite_key)).sum())
            audit["composite_key"] = {
                "columns": list(composite_key),
                "unique": duplicate_count == 0,
                "duplicate_row_count": duplicate_count,
            }
        audit["filename"] = path.name
        audit["size_bytes"] = path.stat().st_size
        audits[table_name] = audit
        paths[table_name] = path
    return audits, paths


def audit_orders(path: Path) -> dict[str, Any]:
    """Audit order-status distribution and important timestamp relationships."""
    frame = read_csv(path)
    result: dict[str, Any] = {
        "status_distribution": [],
        "timestamps": [],
        "time_relationships": [],
    }
    if "order_status" in frame.columns:
        counts = frame["order_status"].value_counts(dropna=False)
        total = len(frame)
        result["status_distribution"] = [
            {
                "order_status": "<NULL>" if pd.isna(status) else str(status),
                "count": int(count),
                "percentage": (int(count) / total * 100) if total else 0.0,
            }
            for status, count in counts.items()
        ]

    parsed: dict[str, pd.Series] = {}
    for column_name in ORDER_TIMESTAMPS:
        if column_name not in frame.columns:
            continue
        source = frame[column_name]
        values = pd.to_datetime(source, errors="coerce")
        parsed[column_name] = values
        result["timestamps"].append(
            {
                "column": column_name,
                "min": _timestamp_text(values.min()),
                "max": _timestamp_text(values.max()),
                "null_count": int(source.isna().sum()),
                "invalid_non_null_count": int((source.notna() & values.isna()).sum()),
                "nulls_by_order_status": {
                    str(status): int(count)
                    for status, count in frame.loc[
                        source.isna(), "order_status"
                    ].value_counts(dropna=False).items()
                }
                if "order_status" in frame.columns
                else {},
            }
        )

    comparisons = (
        (
            "approval_before_purchase",
            "order_approved_at",
            "order_purchase_timestamp",
            "before",
            "chronology anomaly",
        ),
        (
            "carrier_handoff_before_purchase",
            "order_delivered_carrier_date",
            "order_purchase_timestamp",
            "before",
            "chronology anomaly",
        ),
        (
            "customer_delivery_before_purchase",
            "order_delivered_customer_date",
            "order_purchase_timestamp",
            "before",
            "chronology anomaly",
        ),
        (
            "carrier_handoff_before_approval",
            "order_delivered_carrier_date",
            "order_approved_at",
            "before",
            "chronology anomaly",
        ),
        (
            "customer_delivery_before_carrier_handoff",
            "order_delivered_customer_date",
            "order_delivered_carrier_date",
            "before",
            "chronology anomaly",
        ),
        (
            "estimated_delivery_before_purchase",
            "order_estimated_delivery_date",
            "order_purchase_timestamp",
            "before",
            "chronology anomaly",
        ),
        (
            "delivered_after_estimate",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
            "after",
            "service outcome, not necessarily invalid",
        ),
    )
    for name, left_name, right_name, direction, interpretation in comparisons:
        if left_name not in parsed or right_name not in parsed:
            continue
        left = parsed[left_name]
        right = parsed[right_name]
        comparable = left.notna() & right.notna()
        violations = left < right if direction == "before" else left > right
        comparable_count = int(comparable.sum())
        count = int((comparable & violations).sum())
        result["time_relationships"].append(
            {
                "check": name,
                "left_column": left_name,
                "right_column": right_name,
                "comparable_rows": comparable_count,
                "count": count,
                "percentage_of_comparable": (
                    count / comparable_count * 100 if comparable_count else 0.0
                ),
                "interpretation": interpretation,
            }
        )
    return result


def _timestamp_text(value: Any) -> str | None:
    if pd.isna(value):
        return None
    return value.isoformat(sep=" ")


def audit_relationships(paths: dict[str, Path]) -> list[dict[str, Any]]:
    """Measure real parent-child key coverage and observed cardinality."""
    results: list[dict[str, Any]] = []
    for child_table, child_key, parent_table, parent_key in RELATIONSHIPS:
        if child_table not in paths or parent_table not in paths:
            results.append(
                {
                    "relationship": (
                        f"{child_table}.{child_key} -> {parent_table}.{parent_key}"
                    ),
                    "available": False,
                    "reason": "required table file not found",
                }
            )
            continue

        try:
            child = read_csv(paths[child_table], [child_key])[child_key]
            parent = read_csv(paths[parent_table], [parent_key])[parent_key]
        except (AuditError, ValueError, KeyError) as exc:
            results.append(
                {
                    "relationship": (
                        f"{child_table}.{child_key} -> {parent_table}.{parent_key}"
                    ),
                    "available": False,
                    "reason": str(exc),
                }
            )
            continue

        parent_non_null = parent.dropna()
        child_non_null = child.dropna()
        parent_keys = set(parent_non_null.unique())
        matched = child.notna() & child.isin(parent_keys)
        unmatched = ~matched
        parent_unique = bool(parent_non_null.is_unique)
        child_unique = bool(child_non_null.is_unique)
        if parent_unique and child_unique:
            cardinality = "1:1"
        elif parent_unique:
            cardinality = "1:N"
        elif child_unique:
            cardinality = "N:1"
        else:
            cardinality = "N:M"

        results.append(
            {
                "relationship": (
                    f"{child_table}.{child_key} -> {parent_table}.{parent_key}"
                ),
                "available": True,
                "parent_rows": int(len(parent)),
                "parent_null_count": int(parent.isna().sum()),
                "parent_unique_key_count": int(parent_non_null.nunique()),
                "parent_key_unique": parent_unique,
                "parent_duplicate_key_rows": int(
                    parent_non_null.duplicated(keep=False).sum()
                ),
                "child_rows": int(len(child)),
                "child_null_count": int(child.isna().sum()),
                "child_unique_key_count": int(child_non_null.nunique()),
                "matched_child_rows": int(matched.sum()),
                "unmatched_child_rows": int(unmatched.sum()),
                "unmatched_distinct_non_null_keys": int(
                    child_non_null[~child_non_null.isin(parent_keys)].nunique()
                ),
                "match_rate": float(matched.sum() / len(child) * 100)
                if len(child)
                else 0.0,
                "observed_cardinality": cardinality,
            }
        )
    return results


def audit_business_coverage(paths: dict[str, Path]) -> dict[str, Any]:
    """Measure optional child coverage and reference-data gaps useful to support."""
    result: dict[str, Any] = {
        "orders_without_children": {},
        "product_categories_without_translation": [],
        "translation_categories_without_products": [],
        "undefined_payment_type_rows": None,
    }
    if "orders" in paths:
        order_ids = set(read_csv(paths["orders"], ["order_id"])["order_id"].dropna())
        for table_name in ("order_items", "payments", "reviews"):
            if table_name not in paths:
                continue
            child_ids = set(
                read_csv(paths[table_name], ["order_id"])["order_id"].dropna()
            )
            result["orders_without_children"][table_name] = len(order_ids - child_ids)

    if "products" in paths and "category_translation" in paths:
        product_categories = set(
            read_csv(paths["products"], ["product_category_name"])[
                "product_category_name"
            ].dropna()
        )
        translated_categories = set(
            read_csv(paths["category_translation"], ["product_category_name"])[
                "product_category_name"
            ].dropna()
        )
        result["product_categories_without_translation"] = sorted(
            product_categories - translated_categories
        )
        result["translation_categories_without_products"] = sorted(
            translated_categories - product_categories
        )

    if "payments" in paths:
        payment_types = read_csv(paths["payments"], ["payment_type"])[
            "payment_type"
        ]
        result["undefined_payment_type_rows"] = int(
            payment_types.eq("not_defined").sum()
        )
    return result


def render_markdown(
    manifest: dict[str, Any],
    audits: dict[str, Any],
    paths: dict[str, Path],
    orders: dict[str, Any],
    relationships: list[dict[str, Any]],
    business_coverage: dict[str, Any],
) -> str:
    """Render the requested Stage 1 audit as a traceable Markdown report."""
    found_names = {entry["filename"] for entry in manifest["files"]}
    missing = sorted(set(EXPECTED_FILES) - found_names)
    unexpected = sorted(found_names - set(EXPECTED_FILES))
    lines = [
        "# Stage 1 — Olist Real E-Commerce Data Audit",
        "",
        "## 1. Dataset Source",
        "",
        "- Dataset: Olist Brazilian E-Commerce Public Dataset",
        f"- Kaggle slug: `{DATASET_SLUG}`",
        f"- Source: {DATASET_URL}",
        "- License: needs confirmation from a trustworthy source before reuse or redistribution.",
        f"- Audit generated at: `{manifest['generated_at_utc']}`",
        "- Raw CSV files were read without modification.",
        "",
        "## 2. Raw Files",
        "",
        "| Filename | Size (bytes) | SHA256 |",
        "|---|---:|---|",
    ]
    for entry in manifest["files"]:
        lines.append(
            f"| `{entry['filename']}` | {entry['size_bytes']:,} | `{entry['sha256']}` |"
        )
    lines.extend(
        [
            "",
            f"Expected filenames not found: {_code_list(missing)}",
            "",
            f"Additional CSV files found: {_code_list(unexpected)}",
            "",
            "## 3. Table Overview",
            "",
            "| Table | File | Rows | Columns | Exact duplicate rows |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for table_name, audit in audits.items():
        lines.append(
            f"| `{table_name}` | `{audit['filename']}` | "
            f"{audit['row_count']:,} | {audit['column_count']:,} | "
            f"{audit['duplicate_row_count']:,} |"
        )

    lines.extend(["", "## 4. Key Schema", ""])
    for table_name, audit in audits.items():
        lines.extend(
            [
                f"### {table_name}",
                "",
                "| Column | Inferred dtype | Nulls | Null % | Unique | ID uniqueness |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for column in audit["columns"]:
            id_check = "—"
            if column["suspected_id"]:
                id_check = (
                    "unique among non-null values"
                    if column["non_null_unique"]
                    else f"not unique ({column['duplicate_non_null_rows']:,} affected rows)"
                )
            lines.append(
                f"| `{column['name']}` | `{column['dtype']}` | "
                f"{column['null_count']:,} | {column['null_percentage']:.4f}% | "
                f"{column['unique_count']:,} | {id_check} |"
            )
        lines.append("")

    lines.extend(["## 5. Data Quality", ""])
    if missing:
        lines.append(f"- Missing expected files: {_code_list(missing)}")
    if unexpected:
        lines.append(f"- Additional CSV files: {_code_list(unexpected)}")
    duplicate_tables = [
        f"`{name}` ({audit['duplicate_row_count']:,})"
        for name, audit in audits.items()
        if audit["duplicate_row_count"]
    ]
    lines.append(
        "- Tables with exact duplicate rows: "
        + (", ".join(duplicate_tables) if duplicate_tables else "none")
    )
    id_issues = []
    for table_name, audit in audits.items():
        for column in audit["columns"]:
            if column["suspected_id"] and not column["non_null_unique"]:
                id_issues.append(
                    f"`{table_name}.{column['name']}` "
                    f"({column['duplicate_non_null_rows']:,} affected rows)"
                )
    lines.append(
        "- Non-unique suspected ID columns: "
        + (", ".join(id_issues) if id_issues else "none")
    )
    composite_checks = []
    for table_name, audit in audits.items():
        if "composite_key" not in audit:
            continue
        check = audit["composite_key"]
        fields = ", ".join(check["columns"])
        composite_checks.append(
            f"`{table_name}({fields})`: "
            + (
                "unique"
                if check["unique"]
                else f"{check['duplicate_row_count']:,} duplicate rows"
            )
        )
    lines.append(
        "- Candidate composite-key checks: "
        + ("; ".join(composite_checks) if composite_checks else "not available")
    )
    negative_fields = []
    for table_name, audit in audits.items():
        for column in audit["numeric_summary"]:
            if column["negative_count"]:
                negative_fields.append(
                    f"`{table_name}.{column['name']}` ({column['negative_count']:,})"
                )
    lines.append(
        "- Numeric sign scan: "
        + (", ".join(negative_fields) if negative_fields else "no negative values")
        + ". Negative latitude/longitude values are geographically expected for Brazil and are not, by themselves, data-quality failures."
    )
    lines.append(
        "- Nulls must be interpreted by business state; for example, delivery timestamps "
        "can be legitimately absent for cancelled or unavailable orders."
    )
    if business_coverage["orders_without_children"]:
        child_gaps = ", ".join(
            f"`{table}` {count:,}"
            for table, count in business_coverage["orders_without_children"].items()
        )
        lines.append(f"- Orders without a corresponding child record: {child_gaps}.")
    missing_translations = business_coverage[
        "product_categories_without_translation"
    ]
    lines.append(
        "- Product categories without an English translation row: "
        + _code_list(missing_translations)
        + "."
    )
    undefined_payments = business_coverage["undefined_payment_type_rows"]
    if undefined_payments is not None:
        lines.append(
            f"- Payment rows with `payment_type=not_defined`: {undefined_payments:,}."
        )

    lines.extend(
        [
            "",
            "## 6. Order Status Distribution",
            "",
            "| Status | Count | Share |",
            "|---|---:|---:|",
        ]
    )
    for row in orders["status_distribution"]:
        lines.append(
            f"| `{row['order_status']}` | {row['count']:,} | {row['percentage']:.4f}% |"
        )
    if not orders["status_distribution"]:
        lines.append("| unavailable | — | — |")

    lines.extend(
        [
            "",
            "## 7. Timestamp Range",
            "",
            "| Field | Min | Max | Nulls | Invalid non-null values |",
            "|---|---|---|---:|---:|",
        ]
    )
    for row in orders["timestamps"]:
        lines.append(
            f"| `{row['column']}` | `{row['min']}` | `{row['max']}` | "
            f"{row['null_count']:,} | {row['invalid_non_null_count']:,} |"
        )
    lines.extend(["", "Timestamp nulls by order status:", ""])
    for row in orders["timestamps"]:
        if not row["nulls_by_order_status"]:
            lines.append(f"- `{row['column']}`: none")
            continue
        detail = ", ".join(
            f"`{status}` {count:,}"
            for status, count in row["nulls_by_order_status"].items()
        )
        lines.append(f"- `{row['column']}`: {detail}")
    lines.extend(
        [
            "",
            "Observed timestamp relationships:",
            "",
            "| Check | Count | Comparable rows | Rate | Interpretation |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in orders["time_relationships"]:
        lines.append(
            f"| `{row['check']}` | {row['count']:,} | {row['comparable_rows']:,} | "
            f"{row['percentage_of_comparable']:.4f}% | {row['interpretation']} |"
        )
    lines.extend(
        [
            "",
            "Chronology exceptions indicate source-record ordering inconsistencies or differing operational timestamp semantics; they must not be silently corrected. `delivered_after_estimate` is a customer-service lateness signal rather than a chronology error.",
        ]
    )

    lines.extend(
        [
            "",
            "## 8. Table Relationships",
            "",
            "| Relationship | Parent key unique | Child rows | Unmatched rows | "
            "Unmatched distinct keys | Match rate | Observed cardinality |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in relationships:
        if not row["available"]:
            lines.append(
                f"| `{row['relationship']}` | unavailable | — | — | — | — | "
                f"{row['reason']} |"
            )
            continue
        lines.append(
            f"| `{row['relationship']}` | {row['parent_key_unique']} | "
            f"{row['child_rows']:,} | {row['unmatched_child_rows']:,} | "
            f"{row['unmatched_distinct_non_null_keys']:,} | "
            f"{row['match_rate']:.6f}% | {row['observed_cardinality']} |"
        )

    available_columns = {
        table: set(audit["column_names"]) for table, audit in audits.items()
    }
    lines.extend(
        [
            "",
            "## 9. Fields Useful for Customer Support Agent",
            "",
            *_support_field_lines(available_columns),
            "",
            "## 10. Missing Business Fields",
            "",
            "The public Olist transaction files do not provide a complete customer-service "
            "operations model. A later, explicitly synthetic overlay will be needed for:",
            "",
            "- Support ticket ID, channel, queue, priority, reason, lifecycle, SLA, assignee, and resolution.",
            "- Customer name, email, phone number, identity-verification result, and consent/contact preferences.",
            "- Refund request, eligibility decision, approval chain, refund amount, refund status, and settlement timestamp.",
            "- Risk/fraud flags, manual-review outcomes, account notes, and internal escalation history.",
            "- Shipment tracking events, carrier support case IDs, proof of delivery, return merchandise authorization, and return receipt.",
            "- Product warranty rules, defect classification, replacement workflow, inventory availability, and policy exceptions.",
            "",
            "## 11. Risks / Limitations",
            "",
            "- The dataset is a historical marketplace snapshot, not a live operational support system.",
            "- `customer_id` is order-context identity; `customer_unique_id` is the better cross-order customer identifier, but neither provides contact identity.",
            "- Reviews are post-order feedback, not customer-support tickets or verified issue labels.",
            "- Payment rows can be one-to-many per order; aggregations must preserve payment grain.",
            "- Order items can be one-to-many per order and seller/product combinations can repeat; joins can multiply rows.",
            "- Geolocation is large and contains repeated ZIP-prefix coordinates; full ingestion is unnecessary for a compact demo.",
            "- Timestamps have no explicit timezone metadata in the CSV fields; do not infer timezone-dependent SLA behavior without documentation.",
            "- License terms require confirmation from a trustworthy source before redistribution decisions.",
            "",
            "## 12. Recommendations for Stage 2",
            "",
            "- Treat the manifest hashes as the immutable raw-data baseline.",
            "- Define the Stage 2 demo population only after preserving entity and relationship coverage across orders, items, payments, reviews, products, sellers, and customers.",
            "- Keep operational support fields in a clearly labeled synthetic overlay rather than modifying Olist raw records.",
            "- Preserve source keys in downstream tables so every demo record remains traceable to Olist or to the synthetic overlay.",
            "- Consider excluding full geolocation detail from the demo database; retain only fields needed for delivery reasoning or derived regional context.",
        ]
    )
    return "\n".join(lines) + "\n"


def _support_field_lines(columns: dict[str, set[str]]) -> list[str]:
    groups = (
        (
            "CustomerTool",
            {
                "customers": (
                    "customer_id",
                    "customer_unique_id",
                    "customer_zip_code_prefix",
                    "customer_city",
                    "customer_state",
                )
            },
            "customer/order lookup and coarse delivery region",
        ),
        (
            "OrderTool",
            {
                "orders": (
                    "order_id",
                    "customer_id",
                    "order_status",
                    *ORDER_TIMESTAMPS,
                ),
                "order_items": (
                    "order_id",
                    "order_item_id",
                    "product_id",
                    "seller_id",
                    "shipping_limit_date",
                    "price",
                    "freight_value",
                ),
            },
            "order state, item composition, seller, value, and delivery milestones",
        ),
        (
            "RefundTool analysis",
            {
                "payments": (
                    "order_id",
                    "payment_sequential",
                    "payment_type",
                    "payment_installments",
                    "payment_value",
                )
            },
            "original payment context only; no refund workflow is present",
        ),
        (
            "Shipping / Delivery",
            {
                "orders": ORDER_TIMESTAMPS,
                "order_items": ("shipping_limit_date", "freight_value", "seller_id"),
                "customers": ("customer_zip_code_prefix", "customer_city", "customer_state"),
                "sellers": ("seller_zip_code_prefix", "seller_city", "seller_state"),
            },
            "delivery progress, lateness, origin/destination region, and freight context",
        ),
        (
            "Product after-sales",
            {
                "products": (
                    "product_id",
                    "product_category_name",
                    "product_weight_g",
                    "product_length_cm",
                    "product_height_cm",
                    "product_width_cm",
                ),
                "reviews": (
                    "order_id",
                    "review_score",
                    "review_comment_title",
                    "review_comment_message",
                ),
                "category_translation": (
                    "product_category_name",
                    "product_category_name_english",
                ),
            },
            "category, physical attributes, and post-order review signals",
        ),
    )
    lines: list[str] = []
    for tool_name, requested, purpose in groups:
        observed = []
        for table_name, field_names in requested.items():
            for field_name in field_names:
                if field_name in columns.get(table_name, set()):
                    observed.append(f"`{table_name}.{field_name}`")
        lines.append(f"- **{tool_name}:** {', '.join(observed) or 'no expected fields found'} — {purpose}.")
    return lines


def _code_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def run_audit(raw_dir: Path, reports_dir: Path) -> tuple[Path, Path]:
    """Run the full audit and write manifest/report only from discovered real CSVs."""
    files = discover_csv_files(raw_dir)
    if not files:
        raise AuditError(
            f"No CSV files found in {raw_dir}. Download the official Kaggle dataset "
            f"({DATASET_SLUG}) before running the real-data audit."
        )

    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(files)
    manifest_path = reports_dir / "olist_raw_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    audits, paths = audit_tables(files)
    orders = (
        audit_orders(paths["orders"])
        if "orders" in paths
        else {"status_distribution": [], "timestamps": [], "time_relationships": []}
    )
    relationships = audit_relationships(paths)
    business_coverage = audit_business_coverage(paths)
    report_path = reports_dir / "stage1_olist_data_audit.md"
    report_path.write_text(
        render_markdown(
            manifest,
            audits,
            paths,
            orders,
            relationships,
            business_coverage,
        ),
        encoding="utf-8",
    )
    return manifest_path, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/olist"),
        help="Directory containing immutable Olist CSV files.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Directory for the manifest and Markdown audit report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest_path, report_path = run_audit(args.raw_dir, args.reports_dir)
    except AuditError as exc:
        print(f"Audit blocked: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {manifest_path}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
