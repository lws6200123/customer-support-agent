#!/usr/bin/env python3
"""Build the deterministic Stage 2 processed dataset and audit report."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.services.demo_dataset import build_and_write  # noqa: E402


def main() -> int:
    _, metadata = build_and_write()
    print(
        "Built Stage 2 dataset: "
        f"{metadata['selected_order_count']} orders, "
        f"seed={metadata['random_seed']}, "
        f"simulation_now={metadata['simulation_now']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
