"""Build a deterministic, scenario-aware demo dataset from immutable Olist CSVs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from customer_support_agent.core.config import (
    PROCESSED_DATA_DIR,
    RAW_OLIST_DIR,
    REPORTS_DIR,
    STAGE1_MANIFEST_PATH,
    DemoBuildConfig,
)


SOURCE_FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

ORDER_TIME_COLUMNS = {
    "order_purchase_timestamp": "purchase_at",
    "order_approved_at": "approved_at",
    "order_delivered_carrier_date": "carrier_handoff_at",
    "order_delivered_customer_date": "delivered_at",
    "order_estimated_delivery_date": "estimated_delivery_at",
}

PROCESSED_FILES = {
    "customers": "customers.csv",
    "orders": "orders.csv",
    "order_items": "order_items.csv",
    "payments": "payments.csv",
    "reviews": "reviews.csv",
    "products": "products.csv",
    "sellers": "sellers.csv",
    "customer_support_profiles": "customer_support_profiles.csv",
    "tickets": "tickets.csv",
    "refunds": "refunds.csv",
}

CHRONOLOGY_CHECKS = (
    ("approval_before_purchase", "order_approved_at", "order_purchase_timestamp"),
    ("carrier_before_purchase", "order_delivered_carrier_date", "order_purchase_timestamp"),
    ("delivery_before_purchase", "order_delivered_customer_date", "order_purchase_timestamp"),
    ("carrier_before_approval", "order_delivered_carrier_date", "order_approved_at"),
    ("delivery_before_carrier", "order_delivered_customer_date", "order_delivered_carrier_date"),
    ("estimate_before_purchase", "order_estimated_delivery_date", "order_purchase_timestamp"),
)


class DemoBuildError(RuntimeError):
    """Raised when source data cannot produce a trustworthy demo dataset."""


def stable_fraction(seed: int, value: str, salt: str) -> float:
    payload = f"{seed}|{salt}|{value}".encode("utf-8")
    number = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return number / ((1 << 64) - 1)


def stable_int(seed: int, value: str, salt: str, low: int, high: int) -> int:
    if high < low:
        raise ValueError("high must be greater than or equal to low")
    width = high - low + 1
    return low + min(int(stable_fraction(seed, value, salt) * width), width - 1)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_raw_manifest(raw_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Verify immutable raw files against the committed Stage 1 manifest."""
    if not manifest_path.is_file():
        raise DemoBuildError(f"Stage 1 manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest.get("files", []):
        path = raw_dir / entry["filename"]
        if not path.is_file():
            raise DemoBuildError(f"Raw file missing: {entry['filename']}")
        if path.stat().st_size != entry["size_bytes"]:
            raise DemoBuildError(f"Raw file size changed: {entry['filename']}")
        if _sha256_file(path) != entry["sha256"]:
            raise DemoBuildError(f"Raw file hash changed: {entry['filename']}")
    return manifest


def load_source_tables(raw_dir: Path = RAW_OLIST_DIR) -> dict[str, pd.DataFrame]:
    """Load required Olist tables; the large geolocation table is excluded."""
    missing = [name for name in SOURCE_FILES.values() if not (raw_dir / name).is_file()]
    if missing:
        raise DemoBuildError(f"Required Olist files missing: {', '.join(missing)}")
    dtypes: dict[str, dict[str, str]] = {
        "customers": {"customer_id": "string", "customer_unique_id": "string", "customer_zip_code_prefix": "string"},
        "orders": {"order_id": "string", "customer_id": "string"},
        "order_items": {"order_id": "string", "product_id": "string", "seller_id": "string"},
        "payments": {"order_id": "string"},
        "reviews": {"review_id": "string", "order_id": "string"},
        "products": {"product_id": "string"},
        "sellers": {"seller_id": "string", "seller_zip_code_prefix": "string"},
    }
    return {
        table: pd.read_csv(raw_dir / filename, dtype=dtypes.get(table), low_memory=False)
        for table, filename in SOURCE_FILES.items()
    }


def build_order_features(
    tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Construct one row per source order with scenarios and quality flags."""
    orders = tables["orders"].copy()
    for column in ORDER_TIME_COLUMNS:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")
    orders = orders.join(
        tables["order_items"].groupby("order_id").size().rename("item_count"), on="order_id"
    ).join(
        tables["payments"].groupby("order_id").size().rename("payment_count"), on="order_id"
    ).join(
        tables["reviews"].groupby("order_id")["review_score"].min().rename("minimum_review_score"),
        on="order_id",
    )
    orders["item_count"] = orders["item_count"].fillna(0).astype(int)
    orders["payment_count"] = orders["payment_count"].fillna(0).astype(int)

    duplicate_ids = set(
        tables["reviews"].loc[
            tables["reviews"]["review_id"].duplicated(keep=False), "review_id"
        ]
    )
    duplicate_orders = set(
        tables["reviews"].loc[tables["reviews"]["review_id"].isin(duplicate_ids), "order_id"]
    )
    checks = {
        name: orders[left] < orders[right]
        for name, left, right in CHRONOLOGY_CHECKS
    }
    check_frame = pd.DataFrame(checks, index=orders.index)
    orders["source_data_quality_flag"] = check_frame.apply(
        lambda row: ";".join(name for name, value in row.items() if bool(value)) or "none",
        axis=1,
    )
    clean = orders["source_data_quality_flag"].eq("none")
    masks = {
        "delivered_on_time": orders["order_status"].eq("delivered")
        & orders["order_delivered_customer_date"].notna()
        & (orders["order_delivered_customer_date"] <= orders["order_estimated_delivery_date"])
        & clean,
        "delivered_late": orders["order_status"].eq("delivered")
        & orders["order_delivered_customer_date"].notna()
        & (orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"])
        & clean,
        "shipped": orders["order_status"].eq("shipped") & clean,
        "canceled": orders["order_status"].eq("canceled") & clean,
        "unavailable": orders["order_status"].eq("unavailable") & clean,
        "invoiced": orders["order_status"].eq("invoiced") & clean,
        "processing": orders["order_status"].eq("processing") & clean,
        "approved": orders["order_status"].eq("approved") & clean,
        "created": orders["order_status"].eq("created") & clean,
        "low_review": orders["minimum_review_score"].le(2) & clean,
        "multi_item": orders["item_count"].gt(1) & clean,
        "multi_payment": orders["payment_count"].gt(1) & clean,
        "source_chronology_anomaly": ~clean,
        "duplicate_source_review_id": orders["order_id"].isin(duplicate_orders),
    }
    orders = orders.set_index("order_id", drop=False)
    masks = {name: pd.Series(mask.to_numpy(), index=orders.index) for name, mask in masks.items()}
    return orders, masks


def _ranked_candidates(
    candidates: Iterable[str],
    masks: dict[str, pd.Series],
    config: DemoBuildConfig,
    salt: str,
) -> list[str]:
    del masks  # Kept in the signature so the selection strategy remains easy to extend.
    return sorted(
        set(str(value) for value in candidates),
        key=lambda order_id: (
            stable_fraction(config.random_seed, order_id, salt),
            order_id,
        ),
    )


def select_order_ids(
    features: pd.DataFrame,
    masks: dict[str, pd.Series],
    reviews: pd.DataFrame,
    config: DemoBuildConfig,
) -> list[str]:
    """Select an exact-size deterministic union satisfying scenario quotas."""
    selected: set[str] = set()
    duplicated = reviews.loc[reviews["review_id"].duplicated(keep=False)]
    groups = duplicated.groupby("review_id")["order_id"].agg(
        lambda values: tuple(sorted(set(str(value) for value in values)))
    )
    eligible_groups = [(str(review_id), order_ids) for review_id, order_ids in groups.items() if len(order_ids) > 1]
    if eligible_groups:
        _, chosen_orders = min(
            eligible_groups,
            key=lambda item: (
                stable_fraction(config.random_seed, item[0], "duplicate-review-group"),
                item[0],
            ),
        )
        selected.update(chosen_orders)

    for scenario, quota in config.scenario_quotas:
        if scenario not in masks:
            raise DemoBuildError(f"Unknown scenario in configuration: {scenario}")
        candidates = set(features.index[masks[scenario]])
        target = len(candidates) if quota is None else min(quota, len(candidates))
        needed = target - len(selected & candidates)
        if needed > 0:
            ranked = _ranked_candidates(candidates - selected, masks, config, f"scenario:{scenario}")
            selected.update(ranked[:needed])

    if len(selected) > config.target_order_count:
        raise DemoBuildError(
            f"Scenario quotas require {len(selected)} orders, above target {config.target_order_count}"
        )
    fill_pool = features[
        features["source_data_quality_flag"].eq("none")
        & features["item_count"].gt(0)
        & features["payment_count"].gt(0)
    ].index
    ranked_fill = _ranked_candidates(set(fill_pool) - selected, masks, config, "target-fill")
    selected.update(ranked_fill[: config.target_order_count - len(selected)])
    if len(selected) != config.target_order_count:
        raise DemoBuildError(f"Selected {len(selected)} orders; expected {config.target_order_count}")
    for scenario, quota in config.scenario_quotas:
        available = int(masks[scenario].sum())
        expected = available if quota is None else min(quota, available)
        actual = len(selected & set(features.index[masks[scenario]]))
        if actual < expected:
            raise DemoBuildError(f"Scenario {scenario}: selected {actual}, expected {expected}")
    return sorted(selected)


def _timestamp_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat(sep=" ")


def _zip_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text.zfill(5) if text.isdigit() else text


def _order_offset(row: pd.Series, config: DemoBuildConfig) -> pd.Timedelta:
    """Return one deterministic offset for every timestamp belonging to an order."""
    order_id = str(row["order_id"])
    now = pd.Timestamp(config.simulation_now)
    status = str(row["order_status"])
    if status == "delivered" and pd.notna(row["order_delivered_customer_date"]):
        anchor = row["order_delivered_customer_date"]
        days_ago = stable_int(config.random_seed, order_id, "delivered-days-ago", 1, 30)
        target = now - pd.Timedelta(days=days_ago, hours=stable_int(config.random_seed, order_id, "delivered-hour", 0, 11))
    elif status == "shipped" and pd.notna(row["order_estimated_delivery_date"]):
        anchor = row["order_estimated_delivery_date"]
        estimate_delta = stable_int(config.random_seed, order_id, "shipped-estimate-days", -7, 7)
        target = now + pd.Timedelta(days=estimate_delta)
    elif status in {"created", "approved", "invoiced", "processing"}:
        anchor = row["order_purchase_timestamp"]
        target = now - pd.Timedelta(
            days=stable_int(config.random_seed, order_id, "open-days-ago", 1, 14),
            hours=stable_int(config.random_seed, order_id, "open-hour", 0, 11),
        )
    else:
        anchor = row["order_purchase_timestamp"]
        target = now - pd.Timedelta(
            days=stable_int(config.random_seed, order_id, "historical-days-ago", 15, 90),
            hours=stable_int(config.random_seed, order_id, "historical-hour", 0, 11),
        )
    if pd.isna(anchor):
        raise DemoBuildError(f"Order {order_id} has no usable timeline anchor")
    return target - anchor


def _build_profiles(customer_ids: list[str], config: DemoBuildConfig) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for customer_id in customer_ids:
        membership_roll = stable_fraction(config.random_seed, customer_id, "membership")
        membership = (
            "normal" if membership_roll < 0.70 else
            "silver" if membership_roll < 0.88 else
            "gold" if membership_roll < 0.97 else
            "platinum"
        )
        account_roll = stable_fraction(config.random_seed, customer_id, "account-status")
        account_status = "active" if account_roll < 0.96 else "restricted" if account_roll < 0.98 else "suspended"
        language_roll = stable_fraction(config.random_seed, customer_id, "language")
        language = "pt-BR" if language_roll < 0.95 else "en" if language_roll < 0.99 else "es"
        age_days = stable_int(config.random_seed, customer_id, "profile-age", 30, 1_825)
        records.append(
            {
                "customer_id": customer_id,
                "membership_level": membership,
                "risk_flag": stable_fraction(config.random_seed, customer_id, "risk") < 0.03,
                "account_status": account_status,
                "identity_verified": stable_fraction(config.random_seed, customer_id, "verified") < 0.95,
                "preferred_language": language,
                "created_at": _timestamp_text(pd.Timestamp(config.simulation_now) - pd.Timedelta(days=age_days)),
                "data_origin": "synthetic_operational_data",
            }
        )
    return pd.DataFrame(records)


def _build_tickets(orders: pd.DataFrame, config: DemoBuildConfig) -> pd.DataFrame:
    candidates = orders.sort_values("order_id").head(24)
    categories = (
        "DELIVERY",
        "RETURN_REFUND",
        "PRODUCT_AFTER_SALES",
        "OTHER",
        "ACCOUNT",
        "INVOICE",
    )
    records: list[dict[str, Any]] = []
    for position, row in enumerate(candidates.itertuples(index=False), start=1):
        created_at = pd.Timestamp(config.simulation_now) - pd.Timedelta(days=(position % 12) + 1)
        records.append(
            {
                "ticket_id": f"TKT-{position:05d}",
                "customer_id": row.customer_id,
                "order_id": row.order_id,
                "category": categories[(position - 1) % len(categories)],
                "status": "closed" if position <= 18 else "open",
                "decision": "AUTO_RESOLVE" if position <= 18 else None,
                "priority": "high" if position % 7 == 0 else "normal",
                "subject": f"Synthetic historical support example {position:02d}",
                "resolution": "Synthetic historical resolution" if position <= 18 else None,
                "notes": "Synthetic Stage 2 operational example",
                "created_at": _timestamp_text(created_at),
                "updated_at": _timestamp_text(created_at + pd.Timedelta(hours=position % 36 + 1)) if position <= 18 else _timestamp_text(created_at),
                "closed_at": _timestamp_text(created_at + pd.Timedelta(hours=position % 36 + 1)) if position <= 18 else None,
                "data_origin": "synthetic_operational_data",
            }
        )
    return pd.DataFrame(records)


def _build_refunds(
    orders: pd.DataFrame, payments: pd.DataFrame, config: DemoBuildConfig
) -> pd.DataFrame:
    totals = payments.groupby("order_id", as_index=True)["payment_value"].sum()
    candidates = orders[
        orders["status"].isin(["delivered", "canceled", "unavailable"])
        & orders["order_id"].isin(totals.index)
    ].sort_values("order_id").head(8)
    records: list[dict[str, Any]] = []
    for position, row in enumerate(candidates.itertuples(index=False), start=1):
        amount = round(float(totals.loc[row.order_id]) * (1.0 if position % 3 else 0.5), 2)
        requested_at = pd.Timestamp(config.simulation_now) - pd.Timedelta(days=position)
        records.append(
            {
                "refund_id": f"RFD-{position:05d}",
                "order_id": row.order_id,
                "customer_id": row.customer_id,
                "amount": amount,
                "reason": "synthetic_demo_example",
                "status": "approved" if position <= 5 else "pending" if position <= 7 else "rejected",
                "requested_at": _timestamp_text(requested_at),
                "resolved_at": _timestamp_text(requested_at + pd.Timedelta(hours=position + 2)) if position not in {6, 7} else None,
                "data_origin": "synthetic_operational_data",
            }
        )
    return pd.DataFrame(records)


def _build_entities(
    tables: dict[str, pd.DataFrame],
    features: pd.DataFrame,
    masks: dict[str, pd.Series],
    selected_order_ids: list[str],
    config: DemoBuildConfig,
) -> dict[str, pd.DataFrame]:
    selected_set = set(selected_order_ids)
    source_orders = tables["orders"].loc[
        tables["orders"]["order_id"].isin(selected_set)
    ].copy()
    for column in ORDER_TIME_COLUMNS:
        source_orders[column] = pd.to_datetime(source_orders[column], errors="coerce")
    source_orders = source_orders.sort_values("order_id").reset_index(drop=True)

    source_customer_rows = source_orders[["order_id", "customer_id"]].merge(
        tables["customers"], on="customer_id", how="left", validate="one_to_one"
    )
    if source_customer_rows["customer_unique_id"].isna().any():
        raise DemoBuildError("Selected orders contain customer references missing from source customers")

    unique_customer_ids = sorted(source_customer_rows["customer_unique_id"].astype(str).unique())
    customer_id_map = {
        source_id: f"CUST-{position:06d}"
        for position, source_id in enumerate(unique_customer_ids, start=1)
    }
    source_customer_rows["demo_customer_id"] = source_customer_rows["customer_unique_id"].map(customer_id_map)
    # A source customer_unique_id may have several order-context customer rows. The
    # latest selected source order supplies the display location deterministically.
    source_customer_rows = source_customer_rows.merge(
        source_orders[["order_id", "order_purchase_timestamp"]], on="order_id", how="left"
    )
    representatives = (
        source_customer_rows.sort_values(["order_purchase_timestamp", "order_id"])
        .groupby("customer_unique_id", as_index=False)
        .tail(1)
        .sort_values("demo_customer_id")
    )
    customers = pd.DataFrame(
        {
            "customer_id": representatives["demo_customer_id"],
            "source_customer_unique_id": representatives["customer_unique_id"],
            "display_name": representatives["demo_customer_id"].str.replace("CUST-", "Customer-", regex=False),
            "city": representatives["customer_city"],
            "state": representatives["customer_state"],
            "zip_code_prefix": representatives["customer_zip_code_prefix"].map(_zip_text),
            "data_origin": "olist_real_anonymized",
        }
    ).reset_index(drop=True)

    source_context_to_demo = source_customer_rows.set_index("customer_id")["demo_customer_id"]
    order_id_map = {
        source_id: f"ORD-{position:06d}"
        for position, source_id in enumerate(selected_order_ids, start=1)
    }
    offsets: dict[str, pd.Timedelta] = {}
    order_records: list[dict[str, Any]] = []
    for row in source_orders.itertuples(index=False):
        source_order_id = str(row.order_id)
        feature = features.loc[source_order_id]
        offset = _order_offset(feature, config)
        offsets[source_order_id] = offset
        labels = [name for name, mask in masks.items() if bool(mask.get(source_order_id, False))]
        simulated = {
            output: getattr(row, source) + offset if pd.notna(getattr(row, source)) else None
            for source, output in ORDER_TIME_COLUMNS.items()
        }
        if row.order_status == "shipped" and simulated["estimated_delivery_at"] is not None:
            labels.append(
                "shipped_overdue"
                if simulated["estimated_delivery_at"] < pd.Timestamp(config.simulation_now)
                else "shipped_not_overdue"
            )
        record: dict[str, Any] = {
            "order_id": order_id_map[source_order_id],
            "source_order_id": source_order_id,
            "customer_id": str(source_context_to_demo.loc[str(row.customer_id)]),
            "source_customer_id": str(row.customer_id),
            "status": row.order_status,
            "source_data_quality_flag": feature["source_data_quality_flag"],
            "scenario_labels": ";".join(sorted(set(labels))),
            "timeline_offset_seconds": int(offset.total_seconds()),
            "data_origin": "olist_real_anonymized_derived_timeline",
        }
        for source, output in ORDER_TIME_COLUMNS.items():
            record[f"source_{output}"] = _timestamp_text(getattr(row, source))
            record[output] = _timestamp_text(simulated[output])
        order_records.append(record)
    orders = pd.DataFrame(order_records).sort_values("order_id").reset_index(drop=True)

    source_items = tables["order_items"].loc[
        tables["order_items"]["order_id"].isin(selected_set)
    ].copy()
    source_products = sorted(source_items["product_id"].dropna().astype(str).unique())
    source_sellers = sorted(source_items["seller_id"].dropna().astype(str).unique())
    product_id_map = {value: f"PROD-{position:06d}" for position, value in enumerate(source_products, start=1)}
    seller_id_map = {value: f"SELL-{position:06d}" for position, value in enumerate(source_sellers, start=1)}

    product_source = tables["products"].loc[
        tables["products"]["product_id"].isin(source_products)
    ].merge(tables["category_translation"], on="product_category_name", how="left")
    products = pd.DataFrame(
        {
            "product_id": product_source["product_id"].map(product_id_map),
            "source_product_id": product_source["product_id"],
            "category_name": product_source["product_category_name"],
            "category_name_english": product_source["product_category_name_english"],
            "name_length": product_source["product_name_lenght"],
            "description_length": product_source["product_description_lenght"],
            "photos_quantity": product_source["product_photos_qty"],
            "weight_g": product_source["product_weight_g"],
            "length_cm": product_source["product_length_cm"],
            "height_cm": product_source["product_height_cm"],
            "width_cm": product_source["product_width_cm"],
            "data_origin": "olist_real_anonymized",
        }
    ).sort_values("product_id").reset_index(drop=True)

    seller_source = tables["sellers"].loc[
        tables["sellers"]["seller_id"].isin(source_sellers)
    ]
    sellers = pd.DataFrame(
        {
            "seller_id": seller_source["seller_id"].map(seller_id_map),
            "source_seller_id": seller_source["seller_id"],
            "city": seller_source["seller_city"],
            "state": seller_source["seller_state"],
            "zip_code_prefix": seller_source["seller_zip_code_prefix"].map(_zip_text),
            "data_origin": "olist_real_anonymized",
        }
    ).sort_values("seller_id").reset_index(drop=True)

    source_items["source_shipping_limit_at"] = pd.to_datetime(
        source_items["shipping_limit_date"], errors="coerce"
    )
    source_items = source_items.sort_values(["order_id", "order_item_id"]).reset_index(drop=True)
    item_records: list[dict[str, Any]] = []
    for position, row in enumerate(source_items.itertuples(index=False), start=1):
        offset = offsets[str(row.order_id)]
        item_records.append(
            {
                "order_item_id": f"ITEM-{position:07d}",
                "order_id": order_id_map[str(row.order_id)],
                "source_order_item_sequence": int(row.order_item_id),
                "product_id": product_id_map[str(row.product_id)],
                "seller_id": seller_id_map[str(row.seller_id)],
                "source_shipping_limit_at": _timestamp_text(row.source_shipping_limit_at),
                "shipping_limit_at": _timestamp_text(row.source_shipping_limit_at + offset),
                "price": float(row.price),
                "freight_value": float(row.freight_value),
                "data_origin": "olist_real_anonymized_derived_timeline",
            }
        )
    order_items = pd.DataFrame(item_records)

    source_payments = tables["payments"].loc[
        tables["payments"]["order_id"].isin(selected_set)
    ].sort_values(["order_id", "payment_sequential"]).reset_index(drop=True)
    payments = source_payments.assign(
        payment_id=[f"PAY-{position:07d}" for position in range(1, len(source_payments) + 1)],
        order_id=source_payments["order_id"].map(order_id_map),
        source_payment_sequence=source_payments["payment_sequential"].astype(int),
        data_origin="olist_real_anonymized",
    )[
        ["payment_id", "order_id", "source_payment_sequence", "payment_type", "payment_installments", "payment_value", "data_origin"]
    ]

    source_reviews = tables["reviews"].loc[
        tables["reviews"]["order_id"].isin(selected_set)
    ].copy()
    source_reviews["review_creation_date"] = pd.to_datetime(source_reviews["review_creation_date"], errors="coerce")
    source_reviews["review_answer_timestamp"] = pd.to_datetime(source_reviews["review_answer_timestamp"], errors="coerce")
    source_reviews = source_reviews.sort_values(["order_id", "review_id", "review_creation_date"], na_position="last").reset_index(drop=True)
    review_records: list[dict[str, Any]] = []
    for position, row in enumerate(source_reviews.itertuples(index=False), start=1):
        offset = offsets[str(row.order_id)]
        review_records.append(
            {
                "review_row_id": f"REVROW-{position:07d}",
                "source_review_id": str(row.review_id),
                "order_id": order_id_map[str(row.order_id)],
                "review_score": int(row.review_score),
                "review_comment_title": None if pd.isna(row.review_comment_title) else str(row.review_comment_title),
                "review_comment_message": None if pd.isna(row.review_comment_message) else str(row.review_comment_message),
                "source_review_created_at": _timestamp_text(row.review_creation_date),
                "review_created_at": _timestamp_text(row.review_creation_date + offset),
                "source_review_answered_at": _timestamp_text(row.review_answer_timestamp),
                "review_answered_at": _timestamp_text(row.review_answer_timestamp + offset),
                "data_origin": "olist_real_anonymized_derived_timeline",
            }
        )
    reviews = pd.DataFrame(review_records)

    profiles = _build_profiles(customers["customer_id"].tolist(), config)
    entities = {
        "customers": customers,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
        "reviews": reviews,
        "products": products,
        "sellers": sellers,
        "customer_support_profiles": profiles,
    }
    entities["tickets"] = _build_tickets(orders, config)
    entities["refunds"] = _build_refunds(orders, payments, config)
    return entities


def validate_referential_integrity(entities: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Validate every processed relationship and return orphan counts."""
    relationships = {
        "orders.customer_id -> customers.customer_id": (
            entities["orders"]["customer_id"], entities["customers"]["customer_id"]
        ),
        "order_items.order_id -> orders.order_id": (
            entities["order_items"]["order_id"], entities["orders"]["order_id"]
        ),
        "order_items.product_id -> products.product_id": (
            entities["order_items"]["product_id"], entities["products"]["product_id"]
        ),
        "order_items.seller_id -> sellers.seller_id": (
            entities["order_items"]["seller_id"], entities["sellers"]["seller_id"]
        ),
        "payments.order_id -> orders.order_id": (
            entities["payments"]["order_id"], entities["orders"]["order_id"]
        ),
        "reviews.order_id -> orders.order_id": (
            entities["reviews"]["order_id"], entities["orders"]["order_id"]
        ),
        "profiles.customer_id -> customers.customer_id": (
            entities["customer_support_profiles"]["customer_id"], entities["customers"]["customer_id"]
        ),
        "tickets.order_id -> orders.order_id": (
            entities["tickets"]["order_id"], entities["orders"]["order_id"]
        ),
        "refunds.order_id -> orders.order_id": (
            entities["refunds"]["order_id"], entities["orders"]["order_id"]
        ),
    }
    orphan_counts = {
        name: int((~child.isin(set(parent.dropna()))).sum())
        for name, (child, parent) in relationships.items()
    }
    failed = {name: count for name, count in orphan_counts.items() if count}
    if failed:
        raise DemoBuildError(f"Processed referential-integrity failure: {failed}")
    return orphan_counts


def validate_timeline_offsets(orders: pd.DataFrame) -> None:
    """Ensure each non-null source/simulated timestamp uses one order offset."""
    for row in orders.itertuples(index=False):
        expected = int(row.timeline_offset_seconds)
        for output in ORDER_TIME_COLUMNS.values():
            source_value = getattr(row, f"source_{output}")
            simulated_value = getattr(row, output)
            if pd.isna(source_value) and pd.isna(simulated_value):
                continue
            if pd.isna(source_value) or pd.isna(simulated_value):
                raise DemoBuildError(f"Order {row.order_id} has mismatched null timeline values")
            actual = int((pd.Timestamp(simulated_value) - pd.Timestamp(source_value)).total_seconds())
            if actual != expected:
                raise DemoBuildError(f"Order {row.order_id} has inconsistent timestamp offsets")


def scenario_distribution(orders: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for labels in orders["scenario_labels"].fillna(""):
        for label in filter(None, str(labels).split(";")):
            counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def build_demo_data(
    config: DemoBuildConfig | None = None,
    raw_dir: Path = RAW_OLIST_DIR,
    manifest_path: Path = STAGE1_MANIFEST_PATH,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Build all Stage 2 frames in memory without mutating the source data."""
    config = config or DemoBuildConfig()
    verify_raw_manifest(raw_dir, manifest_path)
    tables = load_source_tables(raw_dir)
    features, masks = build_order_features(tables)
    selected_ids = select_order_ids(features, masks, tables["reviews"], config)
    entities = _build_entities(tables, features, masks, selected_ids, config)
    orphan_counts = validate_referential_integrity(entities)
    validate_timeline_offsets(entities["orders"])
    duplicate_review_rows = int(entities["reviews"]["source_review_id"].duplicated(keep=False).sum())
    metadata = {
        "source_dataset": "Olist Brazilian E-Commerce Public Dataset (Kaggle slug: olistbr/brazilian-ecommerce)",
        "source_order_count": int(len(tables["orders"])),
        "random_seed": config.random_seed,
        "simulation_now": config.simulation_now.isoformat(),
        "selected_order_count": int(len(entities["orders"])),
        "selected_source_order_sha256": hashlib.sha256("\n".join(selected_ids).encode("utf-8")).hexdigest(),
        "scenario_distribution": scenario_distribution(entities["orders"]),
        "processed_table_row_counts": {name: int(len(frame)) for name, frame in entities.items()},
        "referential_integrity_orphan_counts": orphan_counts,
        "source_chronology_anomaly_orders": int(entities["orders"]["source_data_quality_flag"].ne("none").sum()),
        "duplicate_source_review_rows": duplicate_review_rows,
        "config": {
            **asdict(config),
            "simulation_now": config.simulation_now.isoformat(),
            "scenario_quotas": [[name, quota] for name, quota in config.scenario_quotas],
        },
    }
    return entities, metadata


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_processed_dataset(
    entities: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    output_dir: Path = PROCESSED_DATA_DIR,
) -> None:
    """Atomically replace each generated CSV and its build metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for table, filename in PROCESSED_FILES.items():
        content = entities[table].to_csv(index=False, lineterminator="\n")
        _atomic_write_text(output_dir / filename, content)
    _atomic_write_text(
        output_dir / "build_metadata.json",
        json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def render_stage2_report(metadata: dict[str, Any], entities: dict[str, pd.DataFrame]) -> str:
    scenarios = metadata["scenario_distribution"]
    rows = metadata["processed_table_row_counts"]
    profiles = entities["customer_support_profiles"]
    membership = profiles["membership_level"].value_counts().sort_index().to_dict()
    account = profiles["account_status"].value_counts().sort_index().to_dict()
    languages = profiles["preferred_language"].value_counts().sort_index().to_dict()
    lines = [
        "# Stage 2 Demo Dataset",
        "",
        "## Source dataset",
        "",
        "The build uses the immutable Olist Brazilian E-Commerce Public Dataset from Kaggle "
        "(`olistbr/brazilian-ecommerce`). The raw CSV files are never rewritten. The geolocation "
        "table is intentionally excluded because the demo does not require its roughly one million rows.",
        "",
        "## Deterministic scenario-aware selection",
        "",
        f"- Source orders: {metadata['source_order_count']:,}",
        f"- Selected unique orders: {metadata['selected_order_count']:,}",
        f"- Random seed: `{metadata['random_seed']}`",
        f"- Selected order-set SHA256: `{metadata['selected_source_order_sha256']}`",
        "- Created and approved orders are fully retained; configured quotas cover shipped, canceled, unavailable, "
        "invoiced, processing, on-time/late delivery, low reviews, multi-item, multi-payment, and source anomalies.",
        "",
        "### Scenario distribution",
        "",
        "Scenarios overlap, so counts do not sum to the selected order count.",
        "",
    ]
    lines.extend(f"- `{name}`: {count:,}" for name, count in scenarios.items())
    lines.extend(
        [
            "",
            "## Customer identity mapping",
            "",
            "Olist `customer_unique_id` is mapped to a stable Demo `CUST-######` identifier. Every "
            "order-context `customer_id` is retained as `source_customer_id`; it is not presented as a "
            "permanent person identifier. Multiple selected orders with the same `customer_unique_id` map "
            "to one Demo customer. Display names are anonymous (`Customer-######`), and no names, email "
            "addresses, or phone numbers are generated.",
            "",
            "## Simulation clock and timeline normalization",
            "",
            f"The fixed business clock is `{metadata['simulation_now']}`. Each order receives exactly one "
            "deterministic offset. That same offset is applied to purchase, approval, carrier handoff, "
            "delivery, estimated delivery, shipping-limit, and review timestamps. Therefore original "
            "intervals and relations—including real late deliveries—remain unchanged.",
            "",
            "Delivered orders are anchored 1–30 days before the clock; shipped estimates are anchored "
            "within ±7 days; active pre-shipment statuses are recent; canceled/unavailable orders are "
            "mapped to recent history. Source chronology anomalies remain flagged and are not repaired.",
            "",
            "## Processed table row counts",
            "",
        ]
    )
    lines.extend(f"- `{name}`: {count:,}" for name, count in rows.items())
    lines.extend(
        [
            "",
            "## Referential integrity",
            "",
        ]
    )
    lines.extend(
        f"- `{relationship}`: {count} orphan rows"
        for relationship, count in metadata["referential_integrity_orphan_counts"].items()
    )
    lines.extend(
        [
            "",
            "## Source anomalies",
            "",
            f"- Selected orders with a source chronology flag: {metadata['source_chronology_anomaly_orders']:,}",
            f"- Selected review rows participating in a duplicated source review ID: {metadata['duplicate_source_review_rows']:,}",
            "- These are preserved as lineage/data-quality facts. Normal business-rule examples should filter "
            "to `source_data_quality_flag = 'none'`.",
            "",
            "## Real, derived, and synthetic boundary",
            "",
            "Olist order status, line items, product attributes, seller location, payments, reviews, and "
            "customer location are real anonymized source facts. Demo IDs, scenario labels, normalized "
            "timestamps, and overdue evaluation are deterministic derivatives.",
            "",
            "Membership level, risk flag, account status, identity verification, preferred language, "
            "support tickets, and refunds are explicitly labeled `synthetic_operational_data`; Olist does "
            "not provide these customer-support operations fields.",
            "",
            "### Synthetic profile distribution",
            "",
            f"- Membership: `{membership}`",
            f"- Account status: `{account}`",
            f"- Preferred language: `{languages}`",
            f"- Risk flagged: {int(profiles['risk_flag'].sum()):,} / {len(profiles):,}",
            f"- Identity verified: {int(profiles['identity_verified'].sum()):,} / {len(profiles):,}",
            "",
            "## Limitations",
            "",
            "The sample is optimized for scenario coverage rather than population-level estimates. Olist lacks "
            "internal case notes, policy decisions, shipment tracking events, return logistics, refund approval "
            "workflow, customer contacts, inventory state, fraud decisions, and agent activity. Synthetic records "
            "exist only to exercise the operational schema and must not be treated as measured Olist behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def build_and_write(
    config: DemoBuildConfig | None = None,
    output_dir: Path = PROCESSED_DATA_DIR,
    report_path: Path | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    entities, metadata = build_demo_data(config=config)
    write_processed_dataset(entities, metadata, output_dir)
    destination = report_path or (REPORTS_DIR / "stage2_demo_dataset.md")
    _atomic_write_text(destination, render_stage2_report(metadata, entities))
    return entities, metadata
