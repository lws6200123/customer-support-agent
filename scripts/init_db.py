#!/usr/bin/env python3
"""Initialize the Stage 2 SQLite database from reproducible processed CSVs."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.core.config import DEMO_DATABASE_PATH  # noqa: E402
from customer_support_agent.db.loader import initialize_database  # noqa: E402


def main() -> int:
    counts = initialize_database()
    print(f"Initialized {DEMO_DATABASE_PATH}")
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
