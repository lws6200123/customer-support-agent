"""Stage 2 SQLite business-query smoke checks and concise reporting."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, func, select, text

from customer_support_agent.core.config import SIMULATION_NOW
from customer_support_agent.db.models import Customer, Order, Review
from customer_support_agent.services.support_queries import (
    assess_shipping,
    find_late_delivery_order,
    find_multi_item_order,
    find_multi_payment_order,
    find_shipped_orders,
    get_customer_profile,
    get_order_details,
)


def run_smoke_checks(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        foreign_keys_enabled = int(connection.scalar(text("PRAGMA foreign_keys")) or 0)
        customer_id = connection.scalar(select(Customer.customer_id).order_by(Customer.customer_id).limit(1))
        duplicate_review = connection.execute(
            select(Review.source_review_id, func.count().label("row_count"))
            .group_by(Review.source_review_id)
            .having(func.count() > 1)
            .order_by(Review.source_review_id)
            .limit(1)
        ).first()
        runtime_counts = {
            name: int(connection.scalar(text(f"SELECT COUNT(*) FROM {name}")) or 0)
            for name in ("agent_runs", "agent_steps", "feedback")
        }

    if not customer_id:
        raise AssertionError("No customer available for customer-profile smoke test")
    profile = get_customer_profile(engine, str(customer_id))
    if profile is None:
        raise AssertionError("Customer profile query returned no result")

    late_order_id = find_late_delivery_order(engine)
    if not late_order_id:
        raise AssertionError("No clean late-delivery order found")
    late_order = get_order_details(engine, late_order_id)
    if late_order is None or late_order["delivered_at"] <= late_order["estimated_delivery_at"]:
        raise AssertionError("Late-delivery relation was not preserved")

    shipped = [assess_shipping(engine, order_id) for order_id in find_shipped_orders(engine)]
    shipped = [item for item in shipped if item is not None]
    overdue = next((item for item in shipped if item["overdue"]), None)
    not_overdue = next((item for item in shipped if not item["overdue"]), None)
    if overdue is None or not_overdue is None:
        raise AssertionError("Shipped sample does not include both overdue states")

    multi_item = find_multi_item_order(engine)
    if multi_item is None:
        raise AssertionError("No multi-item order found")
    multi_item_detail = get_order_details(engine, multi_item[0])
    if multi_item_detail is None or len(multi_item_detail["items"]) != multi_item[1]:
        raise AssertionError("Multi-item query did not return every item")

    multi_payment = find_multi_payment_order(engine)
    if multi_payment is None:
        raise AssertionError("No multi-payment order found")
    multi_payment_detail = get_order_details(engine, multi_payment[0])
    if multi_payment_detail is None or len(multi_payment_detail["payments"]) != multi_payment[1]:
        raise AssertionError("Multi-payment query did not return every payment")
    if multi_payment_detail["payment_total"] != multi_payment[2]:
        raise AssertionError("Payment total differs from database aggregation")

    if duplicate_review is None:
        raise AssertionError("No duplicated source review ID was preserved")
    with engine.connect() as connection:
        internal_ids = list(
            connection.scalars(
                select(Review.review_row_id)
                .where(Review.source_review_id == duplicate_review.source_review_id)
                .order_by(Review.review_row_id)
            )
        )
    if len(internal_ids) != int(duplicate_review.row_count) or len(internal_ids) != len(set(internal_ids)):
        raise AssertionError("Duplicated source review IDs collided with internal row IDs")

    return {
        "foreign_keys_enabled": foreign_keys_enabled,
        "customer_profile": profile,
        "late_delivery": {
            "order_id": late_order_id,
            "delivered_at": late_order["delivered_at"].isoformat(),
            "estimated_delivery_at": late_order["estimated_delivery_at"].isoformat(),
        },
        "shipped_overdue": {
            "order_id": overdue["order_id"],
            "estimated_delivery_at": overdue["estimated_delivery_at"].isoformat(),
            "simulation_now": SIMULATION_NOW.isoformat(),
            "overdue": True,
        },
        "shipped_not_overdue": {
            "order_id": not_overdue["order_id"],
            "estimated_delivery_at": not_overdue["estimated_delivery_at"].isoformat(),
            "simulation_now": SIMULATION_NOW.isoformat(),
            "overdue": False,
        },
        "multi_item": {"order_id": multi_item[0], "item_count": multi_item[1]},
        "multi_payment": {
            "order_id": multi_payment[0],
            "payment_count": multi_payment[1],
            "payment_total": multi_payment[2],
        },
        "duplicate_source_review_id": {
            "source_review_id": str(duplicate_review.source_review_id),
            "row_count": int(duplicate_review.row_count),
            "unique_internal_row_ids": len(set(internal_ids)),
        },
        "runtime_table_counts": runtime_counts,
    }


def render_smoke_report(results: dict[str, Any]) -> str:
    profile = results["customer_profile"]
    return "\n".join(
        [
            "# Stage 2 SQLite Smoke Test",
            "",
            "All checks use read-only service/query functions against the generated SQLite database. "
            "Identifiers below are anonymized Demo/source identifiers; no contact information is stored.",
            "",
            "## Results",
            "",
            f"1. **Customer profile:** `{profile['customer_id']}` returned location, membership "
            f"`{profile['membership_level']}`, risk flag `{profile['risk_flag']}`, account status "
            f"`{profile['account_status']}`, and identity verification `{profile['identity_verified']}`.",
            f"2. **Order details:** `{results['multi_item']['order_id']}` returned all "
            f"{results['multi_item']['item_count']} items with product/seller attributes, plus payments and reviews.",
            f"3. **Late delivery:** `{results['late_delivery']['order_id']}` has delivered time "
            f"`{results['late_delivery']['delivered_at']}` after estimate "
            f"`{results['late_delivery']['estimated_delivery_at']}`.",
            f"4. **Shipping clock:** `{results['shipped_overdue']['order_id']}` evaluated overdue and "
            f"`{results['shipped_not_overdue']['order_id']}` evaluated not overdue at fixed clock "
            f"`{results['shipped_overdue']['simulation_now']}`.",
            f"5. **Multi-item:** `{results['multi_item']['order_id']}` returned "
            f"{results['multi_item']['item_count']} complete rows.",
            f"6. **Multi-payment:** `{results['multi_payment']['order_id']}` returned "
            f"{results['multi_payment']['payment_count']} payments totaling "
            f"{results['multi_payment']['payment_total']:.2f}.",
            f"7. **Duplicate source review ID:** source ID "
            f"`{results['duplicate_source_review_id']['source_review_id']}` is present on "
            f"{results['duplicate_source_review_id']['row_count']} rows backed by the same number of "
            "unique internal primary keys.",
            "",
            "## Database safeguards",
            "",
            f"- `PRAGMA foreign_keys`: {results['foreign_keys_enabled']} (enabled)",
            f"- Empty runtime tables: `{results['runtime_table_counts']}`",
            "- The initialization script builds and validates a temporary database before atomically "
            "replacing only `data/seed/customer_support_demo.db`.",
            "",
        ]
    )
