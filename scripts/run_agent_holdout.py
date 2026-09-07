#!/usr/bin/env python3
"""Run the post-fix holdout exactly once against the frozen system."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from customer_support_agent.agent.schemas import AgentRequest  # noqa: E402
from customer_support_agent.agent.workflow import SupportAgentWorkflow  # noqa: E402
from customer_support_agent.core.config import AppSettings  # noqa: E402
from customer_support_agent.db.engine import create_sqlite_engine  # noqa: E402
from customer_support_agent.llm.adapter import DeepSeekChatModel  # noqa: E402
from scripts.audit_agent_benchmark import EVALUATION_DB_PATH, sha256_file  # noqa: E402
from scripts.audit_agent_holdout import (  # noqa: E402
    HOLDOUT_PATH,
    audit_holdout,
    verify_frozen_files,
)
from scripts.run_agent_benchmark import (  # noqa: E402
    RESULTS_DIR,
    _fmt_number,
    _fmt_ratio,
    compute_metrics,
    evaluate_case,
    failed_case,
    write_case_results,
)


RUN_ID = "HOLDOUT_RUN_1"
RUN_KEY = RUN_ID.lower()
HOLDOUT_REPORT_PATH = PROJECT_ROOT / "reports" / "stage8a_holdout_report.md"


def official_output_paths() -> list[Path]:
    return [
        RESULTS_DIR / f"{RUN_KEY}_cases.csv",
        RESULTS_DIR / f"{RUN_KEY}_cases.json",
        RESULTS_DIR / f"{RUN_KEY}_metadata.json",
        RESULTS_DIR / f"{RUN_KEY}_metrics.json",
        HOLDOUT_REPORT_PATH,
    ]


def ensure_first_official_run() -> None:
    existing = [path for path in official_output_paths() if path.exists()]
    if existing:
        names = ", ".join(path.name for path in existing)
        raise RuntimeError(f"HOLDOUT_RUN_1 is immutable and already exists: {names}")


def write_holdout_report(
    rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    metadata: dict[str, Any],
    path: Path = HOLDOUT_REPORT_PATH,
) -> None:
    failed = [row for row in rows if not row["task_success"]]
    missed = [
        row
        for row in rows
        if row["risk_class"] == "escalation-critical"
        and row["predicted_decision"] != "ESCALATE_TO_HUMAN"
    ]
    lines = [
        "# Stage 8A Post-fix Holdout Sanity Check",
        "",
        "This holdout was created and frozen after the Stage 8A fixes and was not used for subsequent system tuning.",
        "",
        "## Configuration",
        "",
        f"- Run: `{metadata['run_id']}`",
        f"- Cases: {metrics['case_count']}",
        f"- Holdout SHA256: `{metadata['holdout_sha256']}`",
        f"- Frozen system commit: `{metadata['system_freeze_commit']}`",
        f"- DeepSeek model: `{metadata['deepseek_model']}`",
        "- Execution: sequential, real DeepSeek + RAGFlow + frozen LangGraph + real tools",
        "- Runtime: isolated disposable evaluation SQLite database",
        "- Post-result tuning or rerun: prohibited",
        "",
        "## Distribution",
        "",
        f"- Intent: `{metadata['intent_distribution']}`",
        f"- Decision: `{metadata['decision_distribution']}`",
        f"- Escalation-critical: {metadata['escalation_critical']}",
        f"- Information-missing: {metadata['information_missing']}",
        "",
        "## Metrics",
        "",
        f"- Intent Accuracy: {_fmt_ratio(metrics['intent_accuracy'])} ({metrics['intent_correct']}/{metrics['case_count']})",
        f"- Decision Accuracy: {_fmt_ratio(metrics['decision_accuracy'])} ({metrics['decision_correct']}/{metrics['case_count']})",
        f"- Task Success Rate: {_fmt_ratio(metrics['task_success_rate'])} ({metrics['task_success_count']}/{metrics['case_count']})",
        f"- Escalation Precision / Recall / F1: {_fmt_ratio(metrics['escalation']['precision'])} / {_fmt_ratio(metrics['escalation']['recall'])} / {_fmt_ratio(metrics['escalation']['f1'])}",
        f"- Tool Precision / Recall / F1: {_fmt_ratio(metrics['tools']['precision'])} / {_fmt_ratio(metrics['tools']['recall'])} / {_fmt_ratio(metrics['tools']['f1'])}",
        f"- Exact Tool Set Accuracy: {_fmt_ratio(metrics['tools']['exact_set_accuracy'])}",
        f"- Average Tool Calls: {_fmt_number(metrics['average_tool_calls'])}",
        f"- System Error Rate: {_fmt_ratio(metrics['system_error_rate'])} ({metrics['system_error_count']}/{metrics['case_count']})",
        "",
        "## Latency",
        "",
        f"- Mean: {_fmt_number(metrics['latency_ms']['mean'])} ms",
        f"- P50: {_fmt_number(metrics['latency_ms']['p50'])} ms",
        f"- P95: {_fmt_number(metrics['latency_ms']['p95'])} ms",
        f"- Min: {_fmt_number(metrics['latency_ms']['min'])} ms",
        f"- Max: {_fmt_number(metrics['latency_ms']['max'])} ms",
        "",
        "## Failed Cases",
        "",
    ]
    if failed:
        for row in failed:
            lines.extend(
                [
                    f"### {row['case_id']}",
                    "",
                    f"- Expected: `{row['expected_intent']}` / `{row['expected_decision']}`",
                    f"- Actual: `{row['predicted_intent']}` / `{row['predicted_decision']}`",
                    f"- Tool sequence: `{row['actual_tool_sequence']}`",
                    f"- Primary / secondary: `{row['primary_failure']}` / `{row['secondary_failures']}`",
                    f"- Error codes: `{row['error_codes']}`",
                    f"- Safety risk: {'yes' if row['safety_risk'] else 'no'}",
                    "",
                ]
            )
    else:
        lines.extend(["No failed cases.", ""])
    lines.extend(["## Missed Escalation", ""])
    lines.extend(
        [
            f"- `{row['case_id']}` expected escalation but predicted `{row['predicted_decision']}`."
            for row in missed
        ]
        or ["No missed escalation-critical cases."]
    )
    lines.extend(
        [
            "",
            "## Difference from the 60-case Benchmark",
            "",
            "The 60-case benchmark was created before the Stage 8A official runs and was used to identify generalizable implementation defects. This 24-case holdout was authored only after those fixes, uses new messages, is smaller, and is a one-shot sanity check. It does not replace the main benchmark, increase its sample size, or justify production claims.",
            "",
            "## Statistical Boundary",
            "",
            "This is a controlled one-shot portfolio holdout against one configured model and knowledge dataset. It is not production traffic, a production SLA, an industry benchmark, or an independently labeled test set.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_holdout() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    ensure_first_official_run()
    document, errors, summary = audit_holdout()
    if errors:
        raise RuntimeError("Holdout audit failed")
    initial_hash = summary["sha256"]
    settings = AppSettings(database_path=EVALUATION_DB_PATH)
    if not settings.deepseek_configured:
        raise RuntimeError("DeepSeek configuration is missing")
    if not settings.ragflow_configured:
        raise RuntimeError("RAGFlow configuration is missing")
    rules = yaml.safe_load(
        (PROJECT_ROOT / "knowledge" / "business_rules.yaml").read_text(encoding="utf-8")
    )
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
    ).strip()
    if git_commit != document["system_freeze"]["git_commit"]:
        raise RuntimeError("Git commit differs from the declared frozen system commit")
    started_at = datetime.now(timezone.utc)
    engine = create_sqlite_engine(EVALUATION_DB_PATH)
    model = DeepSeekChatModel(settings)
    workflow = SupportAgentWorkflow(model, engine=engine, settings=settings)
    rows: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(document["cases"], start=1):
            try:
                state = workflow.run(
                    AgentRequest(
                        user_message=case["message"],
                        customer_id=case.get("customer_id"),
                        order_id=case.get("order_id"),
                    )
                )
                row = evaluate_case(case, state)
            except Exception as exc:
                row = failed_case(case, exc)
            rows.append(row)
            print(
                f"[{index:02d}/{len(document['cases'])}] {case['case_id']} "
                f"intent={row['predicted_intent']} decision={row['predicted_decision']} "
                f"task={'PASS' if row['task_success'] else 'FAIL'} "
                f"latency_ms={row['latency_ms']:.1f}",
                flush=True,
            )
    finally:
        engine.dispose()
        model.close()
    if sha256_file(HOLDOUT_PATH) != initial_hash:
        raise RuntimeError("Holdout changed during HOLDOUT_RUN_1")
    frozen_errors = verify_frozen_files(document)
    if frozen_errors:
        raise RuntimeError("Frozen Stage 8A or system files changed during HOLDOUT_RUN_1")
    metrics = compute_metrics(rows)
    metadata = {
        "run_id": RUN_ID,
        "official": True,
        "one_shot": True,
        "post_result_tuning": False,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "holdout_path": str(HOLDOUT_PATH.relative_to(PROJECT_ROOT)),
        "holdout_sha256": initial_hash,
        "system_freeze_commit": document["system_freeze"]["git_commit"],
        "deepseek_model": settings.deepseek_model,
        "ragflow_config": {
            "configured": True,
            "top_n": settings.ragflow_top_n,
            "similarity_threshold": settings.ragflow_similarity_threshold,
            "vector_similarity_weight": settings.ragflow_vector_similarity_weight,
            "reranker_configured": bool(settings.ragflow_rerank_id),
        },
        "business_rules_version": rules.get("specification_version"),
        "simulation_clock": settings.simulation_now.isoformat(),
        "execution_mode": "sequential",
        "intent_distribution": summary["intent_distribution"],
        "decision_distribution": summary["decision_distribution"],
        "escalation_critical": summary["escalation_critical"],
        "information_missing": summary["information_missing"],
    }
    json_path, csv_path = write_case_results(rows, RUN_KEY)
    (RESULTS_DIR / f"{RUN_KEY}_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / f"{RUN_KEY}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_holdout_report(rows, metrics, metadata)
    print(f"Case JSON: {json_path}")
    print(f"Case CSV: {csv_path}")
    print(f"Task success: {metrics['task_success_count']}/{metrics['case_count']}")
    print(f"Holdout report: {HOLDOUT_REPORT_PATH}")
    return rows, metrics, metadata


def main() -> int:
    try:
        run_holdout()
    except Exception as exc:
        print(f"Stage 8A holdout blocked safely: {type(exc).__name__}: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
