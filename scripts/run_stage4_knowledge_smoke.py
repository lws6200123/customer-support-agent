#!/usr/bin/env python3
"""Run the Stage 4 real RAGFlow retrieval smoke suite without using an LLM."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_support_agent.core.config import AppSettings  # noqa: E402
from customer_support_agent.services.knowledge_service import RAGFlowRetrievalClient  # noqa: E402


CASES_PATH = PROJECT_ROOT / "knowledge" / "tool_smoke_cases.yaml"
REPORT_PATH = PROJECT_ROOT / "reports" / "stage4_knowledge_smoke.md"


def load_cases(path: Path = CASES_PATH) -> list[dict[str, str]]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = value.get("cases") if isinstance(value, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("Knowledge smoke cases are missing")
    return cases


def run_smoke(
    client: RAGFlowRetrievalClient,
    cases: list[dict[str, str]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        response = client.search(case["query"])
        retrieved = [item.document_id for item in response.results]
        expected = case["expected_document_id"]
        rows.append(
            {
                **case,
                "retrieved": retrieved,
                "scores": [round(item.score, 4) for item in response.results],
                "top1_hit": bool(retrieved and retrieved[0] == expected),
                "top3_hit": expected in retrieved[:3],
            }
        )
    return {
        "rows": rows,
        "top1_hits": sum(row["top1_hit"] for row in rows),
        "top3_hits": sum(row["top3_hit"] for row in rows),
        "case_count": len(rows),
    }


def write_report(result: dict[str, Any], settings: AppSettings) -> None:
    count = result["case_count"]
    lines = [
        "# Stage 4 Knowledge Retrieval Smoke",
        "",
        "## Scope",
        "",
        "This is a real RAGFlow retrieval-only integration smoke test. It does not call an LLM and is not a final evaluation benchmark.",
        "",
        "## Configuration",
        "",
        f"- Retrieval mode: {'configured reranker' if settings.ragflow_rerank_id else 'hybrid baseline without reranker'}",
        f"- Top N: {settings.ragflow_top_n}",
        f"- Similarity threshold: {settings.ragflow_similarity_threshold}",
        f"- Vector similarity weight: {settings.ragflow_vector_similarity_weight}",
        "- API key and dataset identifier: configured locally and intentionally omitted",
        "- Exposed `score`: RAGFlow overall retrieval score; it is not labelled as vector cosine similarity",
        "",
        "## Results",
        "",
        f"- Cases: {count}",
        f"- Top-1 expected hit: {result['top1_hits']}/{count} ({result['top1_hits'] / count:.1%})",
        f"- Top-3 expected hit: {result['top3_hits']}/{count} ({result['top3_hits'] / count:.1%})",
        "",
        "| Case | Expected | Retrieved (ranked) | Scores | Top-1 | Top-3 |",
        "|---|---|---|---|---:|---:|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['case_id']} | {row['expected_document_id']} | "
            f"{', '.join(row['retrieved']) or 'none'} | "
            f"{', '.join(str(score) for score in row['scores']) or 'none'} | "
            f"{'pass' if row['top1_hit'] else 'fail'} | "
            f"{'pass' if row['top3_hit'] else 'fail'} |"
        )
    failures = [row for row in result["rows"] if not row["top3_hit"]]
    lines.extend(["", "## Top-3 Failures", ""])
    if failures:
        for row in failures:
            lines.append(
                f"- `{row['case_id']}` ({row['expected_topic']}): expected "
                f"`{row['expected_document_id']}`, retrieved "
                f"`{', '.join(row['retrieved']) or 'no chunks'}`."
            )
    else:
        lines.append("No Top-3 failures.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "These figures validate only the current small policy corpus and fixed smoke questions. They must not be presented as Agent accuracy, production retrieval quality, or a final benchmark.",
            "",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    settings = AppSettings()
    result = run_smoke(RAGFlowRetrievalClient(settings), load_cases())
    write_report(result, settings)
    print(
        f"Knowledge smoke: Top-1 {result['top1_hits']}/{result['case_count']}; "
        f"Top-3 {result['top3_hits']}/{result['case_count']}"
    )
    print(f"Report: {REPORT_PATH}")
    return 0 if result["top3_hits"] == result["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
