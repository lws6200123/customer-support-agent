#!/usr/bin/env python3
"""Read-only preflight for a local DemoShop development environment."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.core.config import AppSettings  # noqa: E402


MINIMUM_PYTHON = (3, 10)
EXPECTED_OLIST_FILES = {
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
}


@dataclass(frozen=True)
class SetupCheck:
    label: str
    ok: bool
    detail: str


def collect_checks(project_root: Path = PROJECT_ROOT) -> list[SetupCheck]:
    raw_dir = project_root / "data" / "raw" / "olist"
    database = project_root / "data" / "seed" / "customer_support_demo.db"
    required_dirs = [
        project_root / "src" / "customer_support_agent",
        project_root / "knowledge" / "policies",
        project_root / "data" / "raw" / "olist",
        project_root / "data" / "processed",
        project_root / "data" / "seed",
        project_root / "frontend",
    ]
    missing_dirs = [
        str(path.relative_to(project_root)) for path in required_dirs if not path.is_dir()
    ]
    available_raw = {path.name for path in raw_dir.glob("*.csv")} if raw_dir.is_dir() else set()
    missing_raw = sorted(EXPECTED_OLIST_FILES - available_raw)
    env_path = project_root / ".env"
    settings = AppSettings(_env_file=env_path if env_path.is_file() else None)
    database_ready = database.is_file() and database.stat().st_size > 0
    return [
        SetupCheck(
            "Python version",
            sys.version_info[:2] >= MINIMUM_PYTHON,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (requires >= 3.10)",
        ),
        SetupCheck(
            "Required directories",
            not missing_dirs,
            "present" if not missing_dirs else "missing: " + ", ".join(missing_dirs),
        ),
        SetupCheck(
            "Olist raw CSVs",
            not missing_raw,
            f"{len(available_raw & EXPECTED_OLIST_FILES)}/{len(EXPECTED_OLIST_FILES)} expected files"
            + ("" if not missing_raw else "; missing: " + ", ".join(missing_raw)),
        ),
        SetupCheck(
            "Demo SQLite database",
            database_ready,
            "available"
            if database_ready
            else "missing; run the dataset build and database initialization",
        ),
        SetupCheck(
            "Backend .env",
            env_path.is_file(),
            "present" if env_path.is_file() else "missing; copy .env.example to .env",
        ),
        SetupCheck(
            "DeepSeek configuration",
            settings.deepseek_configured,
            "configured" if settings.deepseek_configured else "missing required values",
        ),
        SetupCheck(
            "RAGFlow configuration",
            settings.ragflow_configured,
            "configured" if settings.ragflow_configured else "missing required values",
        ),
    ]


def main() -> int:
    checks = collect_checks()
    for check in checks:
        print(f"{'PASS' if check.ok else 'MISSING':7} {check.label}: {check.detail}")
    passed = all(check.ok for check in checks)
    print(f"OVERALL {'PASS' if passed else 'MISSING'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
