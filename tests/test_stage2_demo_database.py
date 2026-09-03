"""High-value tests for the reproducible Stage 2 dataset and SQLite layer."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from customer_support_agent.core.config import SIMULATION_NOW, DemoBuildConfig
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.db.loader import initialize_database
from customer_support_agent.db.models import Base, CustomerSupportProfile, Review
from customer_support_agent.services.demo_dataset import (
    ORDER_TIME_COLUMNS,
    build_demo_data,
    build_order_features,
    load_source_tables,
    select_order_ids,
    validate_referential_integrity,
    validate_timeline_offsets,
    write_processed_dataset,
)
from customer_support_agent.services.support_queries import (
    assess_shipping,
    find_late_delivery_order,
    find_multi_item_order,
    find_multi_payment_order,
    find_shipped_orders,
    get_order_details,
)


@pytest.fixture(scope="session")
def stage2_data():
    entities, metadata = build_demo_data()
    return entities, metadata


@pytest.fixture(scope="session")
def stage2_engine(stage2_data, tmp_path_factory):
    entities, metadata = stage2_data
    root = tmp_path_factory.mktemp("stage2-db")
    processed = root / "processed"
    database = root / "demo.db"
    write_processed_dataset(entities, metadata, processed)
    initialize_database(processed, database)
    engine = create_sqlite_engine(database)
    yield engine
    engine.dispose()


def test_deterministic_sampling() -> None:
    tables = load_source_tables()
    features, masks = build_order_features(tables)
    first = select_order_ids(features, masks, tables["reviews"], DemoBuildConfig())
    second = select_order_ids(features, masks, tables["reviews"], DemoBuildConfig())
    assert first == second
    assert len(first) == 2_000
    assert len(first) == len(set(first))


def test_processed_referential_integrity(stage2_data) -> None:
    entities, _ = stage2_data
    assert set(validate_referential_integrity(entities).values()) == {0}


def test_customer_identity_uses_source_unique_customer(stage2_data) -> None:
    entities, _ = stage2_data
    customers = entities["customers"]
    orders = entities["orders"]
    source_customers = load_source_tables()["customers"][["customer_id", "customer_unique_id"]]
    expected = orders[["customer_id", "source_customer_id"]].merge(
        source_customers, left_on="source_customer_id", right_on="customer_id"
    )
    mapping = customers.set_index("source_customer_unique_id")["customer_id"].to_dict()
    assert customers["source_customer_unique_id"].is_unique
    assert all(mapping[row.customer_unique_id] == row.customer_id_x for row in expected.itertuples())
    assert customers["display_name"].str.fullmatch(r"Customer-\d{6}").all()


def test_same_order_timestamp_offset_consistency(stage2_data) -> None:
    orders = stage2_data[0]["orders"]
    validate_timeline_offsets(orders)
    for row in orders.itertuples(index=False):
        offsets = {
            int((pd.Timestamp(getattr(row, output)) - pd.Timestamp(getattr(row, f"source_{output}"))).total_seconds())
            for output in ORDER_TIME_COLUMNS.values()
            if pd.notna(getattr(row, output))
        }
        assert offsets == {row.timeline_offset_seconds}


def test_relative_intervals_are_preserved(stage2_data) -> None:
    orders = stage2_data[0]["orders"]
    for left, right in (("purchase_at", "approved_at"), ("purchase_at", "estimated_delivery_at"), ("carrier_handoff_at", "delivered_at")):
        usable = orders[left].notna() & orders[right].notna()
        source_delta = pd.to_datetime(orders.loc[usable, f"source_{right}"]) - pd.to_datetime(orders.loc[usable, f"source_{left}"])
        simulated_delta = pd.to_datetime(orders.loc[usable, right]) - pd.to_datetime(orders.loc[usable, left])
        assert source_delta.equals(simulated_delta)


def test_late_delivery_relation_is_preserved(stage2_data) -> None:
    orders = stage2_data[0]["orders"]
    late = orders[orders["scenario_labels"].str.contains(r"(?:^|;)delivered_late(?:;|$)", regex=True)]
    assert not late.empty
    assert (pd.to_datetime(late["source_delivered_at"]) > pd.to_datetime(late["source_estimated_delivery_at"])).all()
    assert (pd.to_datetime(late["delivered_at"]) > pd.to_datetime(late["estimated_delivery_at"])).all()


def test_sqlite_foreign_keys_are_enforced(stage2_engine) -> None:
    with pytest.raises(IntegrityError):
        with stage2_engine.begin() as connection:
            connection.execute(
                CustomerSupportProfile.__table__.insert(),
                {
                    "customer_id": "CUST-NOT-FOUND",
                    "membership_level": "normal",
                    "risk_flag": False,
                    "account_status": "active",
                    "identity_verified": True,
                    "preferred_language": "pt-BR",
                    "created_at": SIMULATION_NOW,
                    "data_origin": "synthetic_operational_data",
                },
            )


def test_multi_item_query_returns_all_rows(stage2_engine) -> None:
    candidate = find_multi_item_order(stage2_engine)
    assert candidate is not None
    detail = get_order_details(stage2_engine, candidate[0])
    assert detail is not None
    assert len(detail["items"]) == candidate[1] > 1


def test_multi_payment_query_returns_all_rows_and_total(stage2_engine) -> None:
    candidate = find_multi_payment_order(stage2_engine)
    assert candidate is not None
    detail = get_order_details(stage2_engine, candidate[0])
    assert detail is not None
    assert len(detail["payments"]) == candidate[1] > 1
    assert detail["payment_total"] == candidate[2]


def test_duplicate_source_review_id_uses_internal_primary_key(stage2_engine) -> None:
    with stage2_engine.connect() as connection:
        duplicate = connection.execute(
            select(Review.source_review_id, func.count().label("count"))
            .group_by(Review.source_review_id)
            .having(func.count() > 1)
            .limit(1)
        ).first()
        assert duplicate is not None
        internal_ids = list(
            connection.scalars(select(Review.review_row_id).where(Review.source_review_id == duplicate.source_review_id))
        )
    assert len(internal_ids) == duplicate.count
    assert len(internal_ids) == len(set(internal_ids))


def test_simulation_clock_is_reproducible(stage2_engine) -> None:
    assert SIMULATION_NOW == datetime.fromisoformat("2026-09-03T12:00:00")
    late_order = find_late_delivery_order(stage2_engine)
    assert late_order is not None
    shipped_order = find_shipped_orders(stage2_engine)[0]
    implicit = assess_shipping(stage2_engine, shipped_order)
    explicit = assess_shipping(stage2_engine, shipped_order, SIMULATION_NOW)
    assert implicit == explicit
    assert implicit is not None and implicit["simulation_now"] == SIMULATION_NOW
    assert Base.metadata.tables["agent_runs"] is not None
