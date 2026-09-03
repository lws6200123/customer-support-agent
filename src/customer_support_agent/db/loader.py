"""Reproducibly initialize the Stage 2 SQLite database from processed CSVs."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, func, inspect, select, text

from customer_support_agent.core.config import DEMO_DATABASE_PATH, PROCESSED_DATA_DIR
from customer_support_agent.db.engine import create_sqlite_engine
from customer_support_agent.db.models import Base
from customer_support_agent.services.demo_dataset import PROCESSED_FILES


LOAD_ORDER = (
    "customers",
    "products",
    "sellers",
    "orders",
    "order_items",
    "payments",
    "reviews",
    "customer_support_profiles",
    "tickets",
    "refunds",
)


def _convert_value(column, value: str) -> Any:  # type: ignore[no-untyped-def]
    if value == "":
        return None
    if isinstance(column.type, Boolean):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(column.type, Integer):
        return int(float(value))
    if isinstance(column.type, Float):
        return float(value)
    if isinstance(column.type, DateTime):
        from datetime import datetime

        return datetime.fromisoformat(value)
    return value


def _read_table(path: Path, table) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = set(table.columns.keys())
        actual = set(reader.fieldnames or [])
        if actual != expected:
            raise ValueError(
                f"Processed schema mismatch for {table.name}: "
                f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
            )
        return [
            {column.name: _convert_value(column, row[column.name]) for column in table.columns}
            for row in reader
        ]


def initialize_database(
    processed_dir: Path = PROCESSED_DATA_DIR,
    database_path: Path = DEMO_DATABASE_PATH,
) -> dict[str, int]:
    """Build a complete temporary DB, validate it, then atomically replace the target."""
    missing = [
        PROCESSED_FILES[table]
        for table in LOAD_ORDER
        if not (processed_dir / PROCESSED_FILES[table]).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Processed files missing: {', '.join(missing)}")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{database_path.name}.", suffix=".tmp", dir=database_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    engine = create_sqlite_engine(temporary_path)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            for table_name in LOAD_ORDER:
                table = Base.metadata.tables[table_name]
                records = _read_table(processed_dir / PROCESSED_FILES[table_name], table)
                if records:
                    connection.execute(table.insert(), records)
            violations = connection.execute(text("PRAGMA foreign_key_check")).all()
            if violations:
                raise ValueError(f"SQLite foreign-key violations: {violations[:5]}")
        with engine.connect() as connection:
            counts = {
                table_name: int(
                    connection.scalar(
                        select(func.count()).select_from(Base.metadata.tables[table_name])
                    )
                    or 0
                )
                for table_name in Base.metadata.tables
            }
    except BaseException:
        engine.dispose()
        temporary_path.unlink(missing_ok=True)
        raise
    engine.dispose()
    os.replace(temporary_path, database_path)

    validation_engine = create_sqlite_engine(database_path)
    try:
        names = set(inspect(validation_engine).get_table_names())
        expected_names = set(Base.metadata.tables)
        if names != expected_names:
            raise ValueError(f"SQLite table mismatch: expected={expected_names}, actual={names}")
    finally:
        validation_engine.dispose()
    return counts
