# Stage 8A Evaluation Protocol

## Scope and Freeze

The official evaluation uses the version-controlled `data/evaluation/agent_benchmark.yaml` without mutation after audit. The benchmark contains 60 human-reviewed Chinese support requests and anonymous Demo identifiers. Its SHA256, Git commit, configured DeepSeek model, non-secret RAG settings, business-rule version, and simulation clock are recorded before an official run.

The benchmark invokes the real single-Agent application workflow directly: DeepSeek structured output, LangGraph orchestration, Stage 4 tools, deterministic refund rules, RAGFlow retrieval, and SQLite persistence. It does not use the browser, Vue, FastAPI transport, a fake LLM, or production traffic.

Every official run rebuilds `data/evaluation/customer_support_eval.db` from processed Stage 2 data, applies only the declared evaluation fixture, and never writes the seed DB or normal Demo runtime DB. The evaluation DB is ignored by Git.

## Ground Truth

- Intent and tool expectations are human-defined against the canonical taxonomy and guarded workflow contract.
- Identifier, order, customer, profile, payment, scenario, and chronology facts come from the isolated Stage 2 SQLite copy.
- Refund decisions and missing fields are recomputed before the run with `RefundDecisionService` and canonical `business_rules.yaml`.
- Legal, safety, account, source-quality, and missing-information routing follows canonical rules and decision examples rather than model output.
- Agent predictions never overwrite expected values.

## Task Success

A case succeeds only when all conditions are true:

1. the Agent finishes without a fatal/system run failure;
2. predicted intent equals expected intent;
3. predicted decision equals expected decision;
4. every required tool is called at least once;
5. no forbidden or unrelated tool is called;
6. when `expected_missing_fields` is declared, the normalized actual set equals it.

Allowed optional tools do not cause failure. Duplicate calls are retained in the observed sequence but counted once for set-based precision/recall.

## Tool Metrics

Across cases, a called required tool is a true positive, an omitted required tool is a false negative, and a called tool outside both `required_tools` and `allowed_optional_tools` is a false positive. Allowed optional tools are neutral. Precision, recall, and F1 are micro-averaged over these counts. Exact Tool Set Accuracy requires the unique actual tool set to equal the required tool set exactly.

## Decision and Safety Metrics

Decision accuracy is exact match. Per-decision accuracy uses cases whose expected class is that decision. Escalation treats `ESCALATE_TO_HUMAN` as the positive class and reports precision, recall, and F1. Every missed escalation-critical case is listed individually in failure analysis.

## Latency and Errors

Latency uses wall-clock `total_latency_ms` returned by the workflow. Reports include mean, linearly interpolated P50/P95, minimum, and maximum across cases with a recorded non-negative latency. System errors include failed/fatal runs and external/database/config/structured-output error codes. A zero denominator is reported as `N/A`, never as an invented percentage.

## Retrieval Observation

For cases that call `search_knowledge`, the runner records retrieval success/failure and the top normalized policy document identifier when available. Retrieval is observed as part of Agent task execution; this is not a repeat of the Stage 4 retrieval benchmark and thresholds remain frozen for the official run.

## Statistical Honesty

Results describe one controlled 60-case portfolio benchmark against one configured model and knowledge dataset. They are not a production SLA, an industry benchmark, real enterprise traffic, or evidence of industry-leading performance.
