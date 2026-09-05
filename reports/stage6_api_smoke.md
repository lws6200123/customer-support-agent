# Stage 6 API Integration Smoke

## Scope

Bounded localhost HTTP smoke through FastAPI, LangGraph, DeepSeek, Stage 4 tools, SQLite, and RAGFlow. This is not a final evaluation benchmark and performs no financial refund.

## Non-streaming Results

| Case | Endpoint | HTTP | Decision | Expected | Agent latency ms | Result |
|---|---|---:|---|---|---:|---|
| AS-01 | `POST /api/v1/agent/run` | 200 | AUTO_RESOLVE | AUTO_RESOLVE | 24017.9 | PASS |
| AS-02 | `POST /api/v1/agent/run` | 200 | NEED_MORE_INFO | NEED_MORE_INFO | 9400.1 | PASS |
| AS-03 | `POST /api/v1/agent/run` | 200 | ESCALATE_TO_HUMAN | ESCALATE_TO_HUMAN | 18993.9 | PASS |

## SSE Result

- Endpoint: `POST /api/v1/agent/run/stream`
- HTTP status: `200`
- Final decision: `AUTO_RESOLVE`
- Event types: `run_started, classification, tool_started, tool_completed, tool_started, tool_completed, tool_started, tool_completed, decision, final_response, run_completed`
- Result: `PASS`

## Safety

Secrets, full prompts, policy bodies, customer identifiers, order identifiers, and dataset identifiers are omitted. AUTO_RESOLVE is only a decision candidate; no refund was executed.
