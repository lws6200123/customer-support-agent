#!/usr/bin/env python3
"""Run Stage 2 business-query smoke checks and write the report."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.core.config import DEMO_DATABASE_PATH, REPORTS_DIR  # noqa: E402
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from customer_support_agent.services.demo_dataset import _atomic_write_text  # noqa: E402
from customer_support_agent.services.smoke_checks import render_smoke_report, run_smoke_checks  # noqa: E402


def main() -> int:
    engine = create_sqlite_engine(DEMO_DATABASE_PATH)
    try:
        results = run_smoke_checks(engine)
    finally:
        engine.dispose()
    report_path = REPORTS_DIR / "stage2_sqlite_smoke.md"
    _atomic_write_text(report_path, render_smoke_report(results))
    print(f"Stage 2 SQLite smoke checks passed; report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
