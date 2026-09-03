"""Deterministic project paths and Stage 2 demo configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_OLIST_DIR = PROJECT_ROOT / "data" / "raw" / "olist"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
SEED_DATA_DIR = PROJECT_ROOT / "data" / "seed"
REPORTS_DIR = PROJECT_ROOT / "reports"
STAGE1_MANIFEST_PATH = REPORTS_DIR / "olist_raw_manifest.json"
DEMO_DATABASE_PATH = SEED_DATA_DIR / "customer_support_demo.db"

SIMULATION_NOW = datetime.fromisoformat("2026-09-03T12:00:00")
DEMO_RANDOM_SEED = 20260903
DEMO_ORDER_COUNT = 2_000

# Quotas are minimum coverage targets. Scenarios overlap, and the remaining
# capacity is deterministically filled from clean source orders.
SCENARIO_QUOTAS: tuple[tuple[str, int | None], ...] = (
    ("created", None),
    ("approved", None),
    ("shipped", 100),
    ("canceled", 100),
    ("unavailable", 100),
    ("invoiced", 80),
    ("processing", 80),
    ("delivered_late", 250),
    ("delivered_on_time", 500),
    ("low_review", 250),
    ("multi_item", 250),
    ("multi_payment", 200),
    ("source_chronology_anomaly", 10),
)


@dataclass(frozen=True)
class DemoBuildConfig:
    """Inputs that fully determine the generated demo dataset."""

    random_seed: int = DEMO_RANDOM_SEED
    target_order_count: int = DEMO_ORDER_COUNT
    simulation_now: datetime = SIMULATION_NOW
    scenario_quotas: tuple[tuple[str, int | None], ...] = SCENARIO_QUOTAS
